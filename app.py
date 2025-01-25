from flask import Flask, render_template, request, redirect, url_for, jsonify, Response
from datetime import datetime, timedelta
import json
import time
import random
import logging
from collections import deque

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Simple in-memory storage (replace with a database in a real application)
inventory = []
orders = []
history = []
categories = []
company_name = "Inventory Dashboard"

@app.route('/')
def dashboard():
    inventory_count = len(inventory)
    total_sales = sum(order['total'] for order in orders)
    low_stock_products = get_low_stock_products()
    return render_template('dashboard.html', 
                           inventory_count=inventory_count, 
                           total_sales=total_sales, 
                           company_name=company_name,
                           low_stock_products=low_stock_products)

@app.route('/inventory')
def inventory_page():
    return render_template('inventory.html', inventory=inventory, categories=categories)

@app.route('/add_item', methods=['POST'])
def add_item():
    try:
        # Log the incoming request data
        app.logger.debug(f"Received form data: {request.form}")

        # Validate and extract form data
        name = request.form.get('name')
        if not name:
            raise ValueError("Item name is required")

        # If 'name' is 'new', use 'newItemName' instead
        if name == 'new':
            name = request.form.get('newItemName')
            if not name:
                raise ValueError("New item name is required")

        category = request.form.get('category')
        if not category:
            raise ValueError("Category is required")

        # If 'category' is 'new', use 'newCategory' instead
        if category == 'new':
            category = request.form.get('newCategory')
            if not category:
                raise ValueError("New category name is required")

        quantity = request.form.get('quantity')
        if not quantity:
            raise ValueError("Quantity is required")
        try:
            quantity = int(quantity)
            if quantity < 0:
                raise ValueError("Quantity must be a non-negative integer")
        except ValueError:
            raise ValueError("Invalid quantity. Please enter a valid number")

        price = request.form.get('price')
        if not price:
            raise ValueError("Price is required")
        try:
            price = float(price)
            if price < 0:
                raise ValueError("Price must be a non-negative number")
        except ValueError:
            raise ValueError("Invalid price. Please enter a valid number")

        expiry_date = request.form.get('expiry_date')
        if expiry_date:
            try:
                expiry_date = datetime.strptime(expiry_date, "%Y-%m-%d").date()
            except ValueError:
                raise ValueError("Invalid expiry date format. Please use YYYY-MM-DD")

        # Check if item already exists
        existing_item = next((item for item in inventory if item['name'].lower() == name.lower()), None)
        
        if existing_item:
            # Update existing item
            existing_item['quantity'] += quantity
            existing_item['price'] = price
            existing_item['category'] = category
            existing_item['expiry_date'] = expiry_date
            message = f"Item '{name}' quantity updated successfully"
            app.logger.info(f"Updated existing item: {existing_item}")
        else:
            # Add new item
            new_item = {
                'id': len(inventory) + 1,
                'name': name,
                'category': category,
                'quantity': quantity,
                'price': price,
                'expiry_date': expiry_date,
                'date_added': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            inventory.append(new_item)
            if category not in categories:
                categories.append(category)
            message = f"New item '{name}' added successfully"
            app.logger.info(f"Added new item: {new_item}")
        
        history.append({'action': 'Item Updated' if existing_item else 'Item Added', 'item': name, 'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        return jsonify({"success": True, "message": message})
    except ValueError as e:
        app.logger.error(f"ValueError in add_item: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        app.logger.error(f"Unexpected error in add_item: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/orders')
def orders_page():
    return render_template('orders.html', orders=orders, inventory=inventory)

@app.route('/add_order', methods=['POST'])
def add_order():
    global orders
    try:
        customer = request.form['customer']
        items = request.form.getlist('items')
        quantities = request.form.getlist('quantities')
        
        if not customer or not items:
            raise ValueError("Invalid input data")
        
        total = 0
        order_items = []
        for item_name, quantity in zip(items, quantities):
            quantity = int(quantity)
            item_data = next((i for i in inventory if i['name'].lower() == item_name.lower()), None)
            if not item_data:
                raise ValueError(f"Item '{item_name}' not found in inventory")
            if item_data['quantity'] < quantity:
                raise ValueError(f"Insufficient stock for '{item_name}'. Available: {item_data['quantity']}, Requested: {quantity}")
            
            item_total = item_data['price'] * quantity
            total += item_total
            order_items.append({'name': item_name, 'quantity': quantity, 'price': item_data['price']})
            
            # Update inventory
            item_data['quantity'] -= quantity
        
        order = {
            'id': len(orders) + 1,
            'customer': customer,
            'items': order_items,
            'total': total,
            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        orders.append(order)
        history.append({'action': 'Order Placed', 'customer': order['customer'], 'date': order['date']})
        return jsonify({"success": True, "message": "Order added successfully"})
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"An error occurred while adding the order: {str(e)}"}), 500

@app.route('/history')
def history_page():
    return render_template('history.html', history=history)

@app.route('/settings')
def settings_page():
    return render_template('settings.html', company_name=company_name)

@app.route('/update_company_name', methods=['POST'])
def update_company_name():
    global company_name
    company_name = request.form['company_name']
    return jsonify({"success": True, "message": "Company name updated successfully", "new_name": company_name})

@app.route('/analytics')
def analytics_page():
    category_data = get_category_data()
    product_sales_data = get_product_sales_data()
    today_sales_data = get_today_sales_data()
    top_selling_products = get_top_selling_products()
    return render_template('analytics.html', 
                           category_data=category_data,
                           product_sales_data=product_sales_data,
                           today_sales_data=today_sales_data,
                           top_selling_products=top_selling_products)

def get_sales_data():
    sales_by_month = {}
    for order in orders:
        month = datetime.strptime(order['date'], "%Y-%m-%d %H:%M:%S").strftime("%Y-%m")
        sales_by_month[month] = sales_by_month.get(month, 0) + order['total']
    
    sorted_sales = sorted(sales_by_month.items())
    return {
        'labels': [item[0] for item in sorted_sales],
        'data': [item[1] for item in sorted_sales]
    }

def get_category_data():
    category_totals = {
        'price': {},
        'quantity': {}
    }
    for item in inventory:
        if item['category'] not in category_totals['price']:
            category_totals['price'][item['category']] = 0
            category_totals['quantity'][item['category']] = 0
        category_totals['price'][item['category']] += item['quantity'] * item['price']
        category_totals['quantity'][item['category']] += item['quantity']
    
    return {
        'labels': list(category_totals['price'].keys()),
        'price_data': list(category_totals['price'].values()),
        'quantity_data': list(category_totals['quantity'].values())
    }

def get_inventory_mini_data():
    data = deque(maxlen=7)
    for item in inventory:
        data.append(item['quantity'])
    return {
        'labels': list(range(1, len(data) + 1)),
        'data': list(data)
    }

def get_sales_mini_data():
    data = deque(maxlen=7)
    for order in orders:
        data.append(order['total'])
    return {
        'labels': list(range(1, len(data) + 1)),
        'data': list(data)
    }

def get_low_stock_products():
    return [item for item in inventory if item['quantity'] < 5]

def get_top_selling_products():
    product_sales = {}
    product_revenue = {}
    for order in orders:
        for item in order['items']:
            if item['name'] not in product_sales:
                product_sales[item['name']] = 0
                product_revenue[item['name']] = 0
            product_sales[item['name']] += item['quantity']
            product_revenue[item['name']] += item['quantity'] * item['price']
    
    sorted_products = sorted(product_sales.items(), key=lambda x: x[1], reverse=True)
    top_products = []
    for product, quantity in sorted_products[:5]:
        top_products.append({
            'name': product,
            'quantity': quantity,
            'revenue': product_revenue[product]
        })
    return top_products  # Return top 5 selling products with name, quantity, and revenue

def get_product_sales_data():
    product_sales = {}
    for order in orders:
        for item in order['items']:
            if item['name'] not in product_sales:
                product_sales[item['name']] = 0
            product_sales[item['name']] += item['quantity'] * item['price']
    
    return {
        'labels': list(product_sales.keys()),
        'data': list(product_sales.values())
    }

def get_today_sales_data():
    today = datetime.now().date()
    today_sales = {}
    for order in orders:
        order_date = datetime.strptime(order['date'], "%Y-%m-%d %H:%M:%S").date()
        if order_date == today:
            for item in order['items']:
                if item['name'] not in today_sales:
                    today_sales[item['name']] = 0
                today_sales[item['name']] += item['quantity'] * item['price']
    
    return {
        'labels': list(today_sales.keys()),
        'data': list(today_sales.values())
    }

@app.route('/stream')
def stream():
    def event_stream():
        global orders
        while True:
            data = {
                'event': 'update',
                'inventory_count': len(inventory),
                'order_count': len(orders),
                'total_sales': sum(order['total'] for order in orders),
                'low_stock_products': get_low_stock_products()
            }
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(1)
    return Response(event_stream(), mimetype="text/event-stream")

@app.route('/download_report')
def download_report():
    report = {
        'inventory': inventory,
        'orders': orders,
        'history': history
    }
    return Response(
        json.dumps(report, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': 'attachment;filename=report.json'}
    )

@app.route('/get_product/<int:id>')
def get_product(id):
    product = next((item for item in inventory if item['id'] == id), None)
    if product:
        return jsonify(product)
    return jsonify({"error": "Product not found"}), 404

@app.route('/edit_product', methods=['POST'])
def edit_product():
    try:
        product_id = int(request.form['id'])
        product = next((item for item in inventory if item['id'] == product_id), None)
        if not product:
            return jsonify({"success": False, "message": "Product not found"}), 404
        
        product['name'] = request.form['name']
        product['quantity'] = int(request.form['quantity'])
        product['category'] = request.form['category']
        
        return jsonify({"success": True, "message": "Product updated successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

@app.route('/delete_product/<int:id>', methods=['POST'])
def delete_product(id):
    global inventory
    inventory = [item for item in inventory if item['id'] != id]
    return jsonify({"success": True, "message": "Product deleted successfully"})

@app.route('/delete_order/<int:id>', methods=['POST'])
def delete_order(id):
    global orders
    order = next((order for order in orders if order['id'] == id), None)
    if order:
        orders = [o for o in orders if o['id'] != id]
        history.append({
            'action': 'Order Deleted',
            'order_id': order['id'],
            'customer': order['customer'],
            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        return jsonify({"success": True, "message": "Order deleted successfully"})
    return jsonify({"success": False, "message": "Order not found"}), 404

@app.route('/get_order/<int:id>')
def get_order(id):
    order = next((order for order in orders if order['id'] == id), None)
    if order:
        return jsonify(order)
    return jsonify({"error": "Order not found"}), 404

@app.route('/edit_order', methods=['POST'])
def edit_order():
    try:
        order_id = int(request.form['id'])
        order = next((order for order in orders if order['id'] == order_id), None)
        if not order:
            return jsonify({"success": False, "message": "Order not found"}), 404
        
        customer = request.form['customer']
        items = request.form.getlist('items')
        quantities = request.form.getlist('quantities')
        
        if not customer or not items:
            raise ValueError("Invalid input data")
        
        # Revert the inventory changes from the original order
        for item in order['items']:
            inventory_item = next((i for i in inventory if i['name'].lower() == item['name'].lower()), None)
            if inventory_item:
                inventory_item['quantity'] += item['quantity']
        
        total = 0
        order_items = []
        for item_name, quantity in zip(items, quantities):
            quantity = int(quantity)
            item_data = next((i for i in inventory if i['name'].lower() == item_name.lower()), None)
            if not item_data:
                raise ValueError(f"Item '{item_name}' not found in inventory")
            if item_data['quantity'] < quantity:
                raise ValueError(f"Insufficient stock for '{item_name}'. Available: {item_data['quantity']}, Requested: {quantity}")
            
            item_total = item_data['price'] * quantity
            total += item_total
            order_items.append({'name': item_name, 'quantity': quantity, 'price': item_data['price']})
            
            # Update inventory
            item_data['quantity'] -= quantity
        
        # Update the order
        order['customer'] = customer
        order['items'] = order_items
        order['total'] = total
        order['date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        history.append({
            'action': 'Order Updated',
            'order_id': order['id'],
            'customer': order['customer'],
            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        return jsonify({"success": True, "message": "Order updated successfully"})
    except ValueError as e:
        return jsonify({"success": False, "message": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"An error occurred while updating the order: {str(e)}"}), 500

@app.route('/get_item/<int:id>')
def get_item(id):
    item = next((item for item in inventory if item['id'] == id), None)
    if item:
        return jsonify(item)
    return jsonify({"error": "Item not found"}), 404

@app.route('/edit_item', methods=['POST'])
def edit_item():
    try:
        item_id = int(request.form['id'])
        item = next((item for item in inventory if item['id'] == item_id), None)
        if not item:
            return jsonify({"success": False, "message": "Item not found"}), 404
        
        item['name'] = request.form['name']
        item['category'] = request.form['category']
        item['quantity'] = int(request.form['quantity'])
        item['price'] = float(request.form['price'])
        item['expiry_date'] = request.form['expiry_date'] if request.form['expiry_date'] else None
        
        history.append({
            'action': 'Item Updated',
            'item': item['name'],
            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        return jsonify({"success": True, "message": "Item updated successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

@app.route('/delete_item/<int:id>', methods=['POST'])
def delete_item(id):
    global inventory
    item = next((item for item in inventory if item['id'] == id), None)
    if item:
        inventory = [i for i in inventory if i['id'] != id]
        history.append({
            'action': 'Item Deleted',
            'item': item['name'],
            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        return jsonify({"success": True, "message": "Item deleted successfully"})
    return jsonify({"success": False, "message": "Item not found"}), 404

if __name__ == '__main__':
    app.run(debug=True)

