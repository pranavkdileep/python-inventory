from flask import Flask, render_template, request, redirect, url_for, jsonify, Response, send_file, session, flash
from datetime import datetime, timedelta
import json
import time
import random
import logging
from collections import deque
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from functools import wraps
import atexit

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a strong secret key

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Global variables
users = {}  # This will store all user data

def init_user_data(email, username, password):
    """Initialize a new user with empty data structures"""
    users[email] = {
        'username': username,
        'password': password,  # Make sure password is stored
        'inventory': [],
        'inventory_name': 'Inventory System',
        'company_name': 'Inventory Dashboard',
        'orders': [],
        'history': [],
        'categories': [],
        'stocks': []
    }
    return users[email]

def init_user_if_needed(email):
    if email not in users:
        users[email] = {
            'username': session['username'],
            'inventory': [],
            'inventory_name': 'Inventory System',
            'company_name': 'Inventory Dashboard',
            'orders': [],
            'history': [],
            'categories': [],
            'stocks': []
        }
    return users[email]

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Helper functions - make sure these are the ONLY definitions of these functions
def get_low_stock_products(user_email):
    """Get low stock products for specific user"""
    user_data = users[user_email]
    return [item for item in user_data['inventory'] if item.get('quantity', 0) < 10]

def get_category_data(user_email):
    """Get category data for specific user"""
    user_data = users[user_email]
    categories = {}
    category_prices = {}
    
    for item in user_data['inventory']:
        category = item.get('category', 'Uncategorized')
        quantity = item.get('quantity', 0)
        price = item.get('price', 0) * quantity
        
        # Update quantities
        if category in categories:
            categories[category] += quantity
        else:
            categories[category] = quantity
            
        # Update prices
        if category in category_prices:
            category_prices[category] += price
        else:
            category_prices[category] = price
    
    # Ensure we have at least some data
    if not categories:
        categories['No Data'] = 0
        category_prices['No Data'] = 0
        
    # Sort categories by total price
    sorted_categories = sorted(category_prices.items(), key=lambda x: x[1], reverse=True)
    labels = [item[0] for item in sorted_categories]
    price_data = [item[1] for item in sorted_categories]
    quantity_data = [categories[label] for label in labels]
    
    return {
        'labels': labels,
        'price_data': price_data,
        'quantity_data': quantity_data
    }

def get_sales_data(user_email):
    """Get sales data for charts"""
    user_data = users[user_email]
    orders = user_data.get('orders', [])
    
    # Product-wise sales data
    product_sales = {}
    for order in orders:
        for item in order.get('items', []):
            name = item.get('name', 'Unknown')
            quantity = item.get('quantity', 0)
            price = item.get('price', 0) * quantity
            
            if name in product_sales:
                product_sales[name]['quantity'] += quantity
                product_sales[name]['revenue'] += price
            else:
                product_sales[name] = {'quantity': quantity, 'revenue': price}
    
    # Sort products by revenue
    sorted_products = sorted(product_sales.items(), key=lambda x: x[1]['revenue'], reverse=True)
    
    # Today's sales data (by hour)
    today = datetime.now().date()
    hourly_sales = {i: {'revenue': 0, 'quantity': 0} for i in range(24)}  # Initialize all hours
    
    for order in orders:
        order_date = datetime.strptime(order.get('date', ''), "%Y-%m-%d %H:%M:%S").date()
        if order_date == today:
            hour = datetime.strptime(order.get('date', ''), "%Y-%m-%d %H:%M:%S").hour
            hourly_sales[hour]['revenue'] += order.get('total', 0)
            for item in order.get('items', []):
                hourly_sales[hour]['quantity'] += item.get('quantity', 0)
    
    return {
        'product': {
            'labels': [item[0] for item in sorted_products[:10]],  # Top 10 products
            'revenue_data': [item[1]['revenue'] for item in sorted_products[:10]],
            'quantity_data': [item[1]['quantity'] for item in sorted_products[:10]]
        },
        'today': {
            'labels': [f'{i:02d}:00' for i in range(24)],
            'data': [hourly_sales[i]['revenue'] for i in range(24)],
            'quantity_data': [hourly_sales[i]['quantity'] for i in range(24)]
        }
    }

def get_inventory_data(user_email):
    """Get both category and item-wise inventory data"""
    user_data = users[user_email]
    
    # Initialize empty dictionaries
    categories = {}
    category_prices = {}
    items = {}
    item_prices = {}
    
    # Process inventory data
    for item in user_data.get('inventory', []):
        category = item.get('category', 'Uncategorized')
        name = item.get('name', 'Unknown')
        quantity = float(item.get('quantity', 0))
        price = float(item.get('price', 0)) * quantity
        
        # Update category data
        if category in categories:
            categories[category] += quantity
            category_prices[category] += price
        else:
            categories[category] = quantity
            category_prices[category] = price
            
        # Update item data
        if name in items:
            items[name] += quantity
            item_prices[name] += price
        else:
            items[name] = quantity
            item_prices[name] = price
    
    # Ensure we have at least some data
    if not categories:
        categories['No Data'] = 0
        category_prices['No Data'] = 0
    
    if not items:
        items['No Items'] = 0
        item_prices['No Items'] = 0
    
    # Sort categories by total price
    sorted_categories = sorted(category_prices.items(), key=lambda x: x[1], reverse=True)
    category_labels = [item[0] for item in sorted_categories]
    category_price_data = [item[1] for item in sorted_categories]
    category_quantity_data = [categories[label] for label in category_labels]
    
    # Sort items by total price
    sorted_items = sorted(item_prices.items(), key=lambda x: x[1], reverse=True)
    item_labels = [item[0] for item in sorted_items]
    item_price_data = [item[1] for item in sorted_items]
    item_quantity_data = [items[label] for label in item_labels]
    
    return {
        'category': {
            'labels': category_labels,
            'price_data': category_price_data,
            'quantity_data': category_quantity_data
        },
        'item': {
            'labels': item_labels,
            'price_data': item_price_data,
            'quantity_data': item_quantity_data
        }
    }

def get_forecasting_data(user_email):
    """Get forecasting data for specific user"""
    user_data = users[user_email]
    forecast = {}
    
    # Calculate average daily sales for each product
    for order in user_data['orders']:
        order_date = datetime.strptime(order['date'], "%Y-%m-%d %H:%M:%S").date()
        days_ago = (datetime.now().date() - order_date).days
        if days_ago <= 30:  # Consider last 30 days
            for item in order['items']:
                name = item['name']
                if name not in forecast:
                    forecast[name] = {
                        'total_quantity': 0,
                        'days_with_sales': set()
                    }
                forecast[name]['total_quantity'] += item['quantity']
                forecast[name]['days_with_sales'].add(order_date)
    
    # Calculate forecasted stock needs
    forecast_data = {}
    for name, data in forecast.items():
        avg_daily_sales = data['total_quantity'] / max(len(data['days_with_sales']), 1)
        forecast_data[name] = max(0, avg_daily_sales * 7)  # 7-day forecast
    
    # Sort by forecasted quantity
    sorted_forecast = sorted(forecast_data.items(), 
                           key=lambda x: x[1],
                           reverse=True)[:10]  # Top 10 items
    
    # Ensure we have at least some data
    if not sorted_forecast:
        return {
            'labels': ['No Data'],
            'data': [0]
        }
    
    return {
        'labels': [item[0] for item in sorted_forecast],
        'data': [item[1] for item in sorted_forecast]
    }

def format_indian_currency(amount):
    s = f"{amount:.2f}"
    integer_part, decimal_part = s.split(".")
    integer_part = "{:,}".format(int(integer_part)).replace(",", ",")
    return f"₹{integer_part}.{decimal_part}"

def cleanup():
    """Function to clear in-memory data."""
    global users
    users.clear()
    print("Cleanup: Cleared all in-memory data.")

# Register the cleanup function to be called on exit
atexit.register(cleanup)

# Home route (redirects to login or dashboard based on session)
@app.route('/')
def home():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = users.get(email)
        
        if user and user.get('password') == password:
            session['user_email'] = email
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html', company_name="Inventory Dashboard")

# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        username = request.form['username']
        
        # Initialize user data with necessary keys
        users[email] = {
            'password': password,
            'username': username,
            'inventory': [],
            'inventory_name': 'Inventory System',
            'company_name': 'Inventory Dashboard',  # Add default company name
            'orders': [],
            'history': [],
            'categories': [],
            'stocks': []
        }
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

# Logout route
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Dashboard route (protected)
@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    user_email = session['user_email']
    user_data = init_user_if_needed(user_email)
    username = session['username']
    
    if request.method == 'POST':
        # Update inventory name
        new_inventory_name = request.form.get('inventory_name')
        if new_inventory_name:
            user_data['inventory_name'] = new_inventory_name
            flash('Inventory name updated successfully!', 'success')
    
    # Calculate dashboard metrics
    inventory_count = len(user_data['inventory'])
    total_sales = sum(float(order.get('total', 0)) for order in user_data['orders'])
    low_stock_products = get_low_stock_products(user_email)
    
    # Get analytics data for mini charts
    sales_mini_data = get_sales_mini_data(user_email)
    inventory_mini_data = get_inventory_mini_data(user_email)
    product_sales_data = get_product_sales_data(user_email)
    today_sales_data = get_today_sales_data(user_email)
    
    return render_template('dashboard.html', 
                         inventory_count=inventory_count,
                         total_sales=total_sales,
                         company_name=user_data['company_name'],  # Use user-specific company name
                         low_stock_products=low_stock_products,
                         orders=user_data['orders'],
                         sales_mini_data=sales_mini_data,
                         inventory_mini_data=inventory_mini_data,
                         product_sales_data=product_sales_data,
                         today_sales_data=today_sales_data,
                         username=username,
                         inventory_name=user_data['inventory_name'])

# Orders route (protected)
@app.route('/orders')
@login_required
def orders_page():
    user_email = session['user_email']
    user_data = init_user_if_needed(user_email)
    return render_template('orders.html', 
                         orders=user_data['orders'], 
                         inventory=user_data['inventory'],
                         company_name=user_data['company_name'])

# Add order route (protected)
@app.route('/add_order', methods=['POST'])
@login_required
def add_order():
    try:
        user_email = session['user_email']
        user_data = users[user_email]
        
        # Get form data
        customer = request.form.get('customer')
        items = request.form.getlist('items')
        quantities = request.form.getlist('quantities')
        
        if not customer or not items:
            return jsonify({
                "success": False,
                "message": "Invalid input data"
            }), 400
        
        order_items = []
        total = 0
        
        # Process each item in the order
        for item_name, quantity in zip(items, quantities):
            quantity = int(quantity)
            
            # Find the item in inventory
            inventory_item = next(
                (item for item in user_data['inventory'] if item['name'] == item_name),
                None
            )
            
            if not inventory_item:
                return jsonify({
                    "success": False,
                    "message": f"Item '{item_name}' not found in inventory"
                }), 404
            
            if inventory_item['quantity'] < quantity:
                return jsonify({
                    "success": False,
                    "message": f"Insufficient stock for '{item_name}'"
                }), 400
            
            # Update inventory quantity
            inventory_item['quantity'] -= quantity
            
            # Add item to order
            item_total = quantity * inventory_item['price']
            order_items.append({
                'name': item_name,
                'quantity': quantity,
                'price': inventory_item['price']
            })
            total += item_total
        
        # Create new order
        order = {
            'id': len(user_data['orders']) + 1,
            'customer': customer,
            'items': order_items,
            'total': total,
            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Add order to user's orders
        user_data['orders'].append(order)
        
        # Add to history
        user_data['history'].append({
            'action': 'Order Created',
            'order_id': order['id'],
            'customer': customer,
            'date': order['date']
        })
        
        return jsonify({
            "success": True,
            "message": "Order added successfully",
            "order": order
        })
        
    except Exception as e:
        print(f"Error adding order: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

# Protect all other routes
@app.before_request
def require_login():
    allowed_routes = ['login', 'register', 'static']
    if request.endpoint not in allowed_routes and 'username' not in session:
        flash('Please login to access this page.', 'error')
        return redirect(url_for('login'))

# Inventory route
@app.route('/inventory')
@login_required
def inventory_page():
    user_email = session['user_email']
    user_data = init_user_if_needed(user_email)
    return render_template('inventory.html', 
                         inventory=user_data['inventory'], 
                         categories=user_data['categories'],
                         company_name=user_data['company_name'])

# Add item route
@app.route('/add_item', methods=['POST'])
@login_required
def add_item():
    try:
        user_email = session['user_email']
        user_data = init_user_if_needed(user_email)
        
        # Get form data
        name = request.form.get('name')
        if request.form.get('name') == 'new':
            name = request.form.get('newItemName')
        
        category = request.form.get('category')
        if category == 'new':
            category = request.form.get('newCategory')
        
        quantity = int(request.form.get('quantity', 0))
        price = float(request.form.get('price', 0))
        
        # Check if item already exists
        existing_item = next(
            (item for item in user_data['inventory'] if 
             item['name'].lower() == name.lower() and 
             item['category'].lower() == category.lower() and
             item['price'] == price),
            None
        )
        
        if existing_item:
            # Update existing item quantity
            existing_item['quantity'] += quantity
            message = "Item quantity updated successfully"
        else:
            # Create new item
            item = {
                'id': len(user_data['inventory']) + 1,
                'name': name,
                'category': category,
                'quantity': quantity,
                'price': price,
                'expiry_date': request.form.get('expiry_date'),
                'date_added': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Add to user's inventory
            user_data['inventory'].append(item)
            message = "Item added successfully"
        
        # Add to user's history
        user_data['history'].append({
            'action': 'Item Added/Updated',
            'item': name,
            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # Add category if it's new
        if category not in user_data['categories']:
            user_data['categories'].append(category)
        
        return jsonify({"success": True, "message": message})
    
    except Exception as e:
        print(f"Error adding item: {e}")
        return jsonify({"success": False, "message": str(e)}), 400

@app.route('/history')
@login_required
def history_page():
    user_email = session['user_email']
    user_data = init_user_if_needed(user_email)
    return render_template('history.html', 
                         history=user_data['history'], 
                         company_name=user_data['company_name'])

@app.route('/settings')
@login_required
def settings_page():
    user_email = session['user_email']
    user_data = init_user_if_needed(user_email)
    return render_template('settings.html', 
                         company_name=user_data['company_name'])

@app.route('/update_company_name', methods=['POST'])
@login_required
def update_company_name():
    user_email = session['user_email']
    user_data = init_user_if_needed(user_email)
    user_data['company_name'] = request.form['company_name']
    return jsonify({
        "success": True, 
        "message": "Company name updated successfully", 
        "new_name": user_data['company_name']
    })

@app.route('/analytics')
@login_required
def analytics_page():
    user_email = session['user_email']
    user_data = init_user_if_needed(user_email)
    
    # Get inventory data for charts
    inventory_data = get_inventory_data(user_email)
    
    # Get sales data
    sales_data = get_sales_data(user_email)
    
    # Get top products
    top_products = get_top_products(user_email)
    
    return render_template('analytics.html',
                         inventory_data=inventory_data,
                         sales_data=sales_data,
                         top_products=top_products,
                         company_name=user_data.get('company_name', 'Inventory Dashboard'))

def get_sales_mini_data(user_email):
    """Get recent sales data for mini chart"""
    user_data = users[user_email]
    recent_orders = sorted(user_data['orders'], 
                         key=lambda x: datetime.strptime(x['date'], "%Y-%m-%d %H:%M:%S"),
                         reverse=True)[:7]
    data = [order.get('total', 0) for order in recent_orders]
    labels = [datetime.strptime(order['date'], "%Y-%m-%d %H:%M:%S").strftime("%d/%m")
             for order in recent_orders]
    return {
        'labels': labels,
        'data': data
    }

def get_inventory_mini_data(user_email):
    """Get inventory data for mini chart"""
    user_data = users[user_email]
    recent_items = sorted(user_data['inventory'], 
                        key=lambda x: x.get('quantity', 0),
                        reverse=True)[:7]
    return {
        'labels': [item.get('name', '') for item in recent_items],
        'data': [item.get('quantity', 0) for item in recent_items]
    }

def get_product_sales_data(user_email):
    """Get product sales data"""
    user_data = users[user_email]
    product_sales = {}
    for order in user_data['orders']:
        for item in order['items']:
            name = item['name']
            if name not in product_sales:
                product_sales[name] = 0
            product_sales[name] += item['quantity'] * item['price']
    
    # Sort by sales value and get top 5
    sorted_sales = sorted(product_sales.items(), key=lambda x: x[1], reverse=True)[:5]
    return {
        'labels': [item[0] for item in sorted_sales],
        'data': [item[1] for item in sorted_sales]
    }

def get_today_sales_data(user_email):
    """Get today's sales data"""
    user_data = users[user_email]
    today = datetime.now().date()
    today_sales = {}
    
    for order in user_data['orders']:
        order_date = datetime.strptime(order['date'], "%Y-%m-%d %H:%M:%S").date()
        if order_date == today:
            for item in order['items']:
                name = item['name']
                if name not in today_sales:
                    today_sales[name] = 0
                today_sales[name] += item['quantity'] * item['price']
    
    return {
        'labels': list(today_sales.keys()),
        'data': list(today_sales.values())
    }

def get_top_products(user_email):
    """Get top selling products"""
    user_data = users[user_email]
    orders = user_data.get('orders', [])
    
    # Aggregate product sales
    product_sales = {}
    for order in orders:
        for item in order.get('items', []):
            name = item.get('name', 'Unknown')
            quantity = item.get('quantity', 0)
            price = item.get('price', 0)
            revenue = price * quantity
            
            if name in product_sales:
                product_sales[name]['quantity'] += quantity
                product_sales[name]['revenue'] += revenue
            else:
                product_sales[name] = {
                    'name': name,
                    'quantity': quantity,
                    'revenue': revenue
                }
    
    # Convert to list and sort by revenue
    top_products = list(product_sales.values())
    top_products.sort(key=lambda x: x['revenue'], reverse=True)
    
    return top_products[:5]  # Return top 5 products

@app.route('/stream')
@login_required
def stream():
    user_email = session['user_email']
    user_data = init_user_if_needed(user_email)
    def event_stream():
        while True:
            try:
                with app.app_context():
                    with app.test_request_context():
                        if 'user_email' in session:
                            user_email = session['user_email']
                            user_data = users.get(user_email, {
                                'inventory': [],
                                'orders': [],
                                'stocks': []
                            })
                            
                            data = {
                                'event': 'update',
                                'inventory_count': len(user_data['inventory']),
                                'order_count': len(user_data['orders']),
                                'total_sales': sum(order.get('total', 0) for order in user_data['orders']),
                                'low_stock_products': get_low_stock_products(user_email)
                            }
                            
                            yield f"data: {json.dumps(data)}\n\n"
                time.sleep(5)
            except Exception as e:
                print(f"Stream error: {e}")
                time.sleep(5)
    
    return Response(event_stream(), mimetype="text/event-stream")

@app.route('/generate_report')
@login_required
def generate_report():
    user_email = session['user_email']
    user_data = users[user_email]
    
    # Create a PDF buffer
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=1  # Center alignment
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=20,
        textColor=colors.HexColor('#666666')
    )
    
    # Add company name and report title
    elements.append(Paragraph(user_data.get('company_name', 'Company Name'), title_style))
    elements.append(Paragraph('Sales Report', subtitle_style))
    
    # Add date range
    current_date = datetime.now().strftime("%Y-%m-%d")
    date_text = f"Generated on: {current_date}"
    elements.append(Paragraph(date_text, styles['Normal']))
    elements.append(Spacer(1, 20))
    
    # Sales Summary Table
    orders = user_data.get('orders', [])
    total_revenue = sum(order.get('total', 0) for order in orders)
    total_orders = len(orders)
    
    summary_data = [
        ['Sales Summary', ''],
        ['Total Revenue', f"₹{total_revenue:,.2f}"],
        ['Total Orders', str(total_orders)],
        ['Average Order Value', f"₹{(total_revenue/total_orders if total_orders > 0 else 0):,.2f}"]
    ]
    
    summary_table = Table(summary_data, colWidths=[200, 200])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8f9fa')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#666666')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#dee2e6')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 30))
    
    # Product-wise Sales Table
    product_sales = {}
    for order in orders:
        for item in order.get('items', []):
            name = item.get('name', 'Unknown')
            quantity = item.get('quantity', 0)
            price = item.get('price', 0)
            revenue = price * quantity
            
            if name in product_sales:
                product_sales[name]['quantity'] += quantity
                product_sales[name]['revenue'] += revenue
            else:
                product_sales[name] = {'quantity': quantity, 'revenue': revenue}
    
    # Sort products by revenue
    sorted_products = sorted(product_sales.items(), key=lambda x: x[1]['revenue'], reverse=True)
    
    # Product Sales Table
    elements.append(Paragraph('Product-wise Sales', subtitle_style))
    
    product_data = [['Product Name', 'Quantity Sold', 'Revenue']]
    for product_name, data in sorted_products:
        product_data.append([
            product_name,
            str(data['quantity']),
            f"₹{data['revenue']:,.2f}"
        ])
    
    product_table = Table(product_data, colWidths=[200, 100, 100])
    product_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8f9fa')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#666666')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#dee2e6')),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
    ]))
    elements.append(product_table)
    elements.append(Spacer(1, 30))
    
    # Recent Orders Table
    elements.append(Paragraph('Recent Orders', subtitle_style))
    
    # Sort orders by date
    sorted_orders = sorted(orders, key=lambda x: datetime.strptime(x.get('date', ''), "%Y-%m-%d %H:%M:%S"), reverse=True)
    recent_orders = sorted_orders[:10]  # Get last 10 orders
    
    order_data = [['Order Date', 'Customer', 'Total']]
    for order in recent_orders:
        order_date = datetime.strptime(order.get('date', ''), "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
        order_data.append([
            order_date,
            order.get('customer', 'Unknown'),
            f"₹{order.get('total', 0):,.2f}"
        ])
    
    order_table = Table(order_data, colWidths=[133, 133, 133])
    order_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8f9fa')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#666666')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#dee2e6')),
        ('ALIGN', (-1, 1), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
    ]))
    elements.append(order_table)
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    return send_file(
        buffer,
        download_name=f'sales_report_{current_date}.pdf',
        as_attachment=True,
        mimetype='application/pdf'
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

@app.route('/get_order/<int:id>')
@login_required
def get_order(id):
    user_email = session['user_email']
    user_data = users[user_email]
    
    order = next((order for order in user_data['orders'] if order['id'] == id), None)
    if order:
        return jsonify(order)
    return jsonify({"error": "Order not found"}), 404

@app.route('/delete_order/<int:id>', methods=['POST'])
@login_required
def delete_order(id):
    user_email = session['user_email']
    user_data = users[user_email]
    
    order = next((order for order in user_data['orders'] if order['id'] == id), None)
    if order:
        # Restore inventory quantities
        for item in order['items']:
            inventory_item = next((inv for inv in user_data['inventory'] if inv['id'] == item['id']), None)
            if inventory_item:
                inventory_item['quantity'] += item['quantity']
        
        # Remove order
        user_data['orders'] = [o for o in user_data['orders'] if o['id'] != id]
        
        # Add to history
        user_data['history'].append({
            'action': 'Order Deleted',
            'order_id': id,
            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        return jsonify({"success": True, "message": "Order deleted successfully"})
    return jsonify({"success": False, "message": "Order not found"}), 404

@app.route('/edit_order', methods=['POST'])
@login_required
def edit_order():
    try:
        user_email = session['user_email']
        user_data = users[user_email]
        
        order_id = int(request.form['id'])
        customer = request.form['customer']
        items = request.form.getlist('items')
        quantities = request.form.getlist('quantities')
        
        # Find the order
        order = next((o for o in user_data['orders'] if o['id'] == order_id), None)
        if not order:
            return jsonify({
                "success": False,
                "message": "Order not found"
            }), 404
        
        # Restore previous inventory quantities
        for item in order['items']:
            inv_item = next((i for i in user_data['inventory'] if i['name'] == item['name']), None)
            if inv_item:
                inv_item['quantity'] += item['quantity']
        
        # Process new order items
        new_items = []
        total = 0
        
        for item_name, quantity in zip(items, quantities):
            quantity = int(quantity)
            inv_item = next((i for i in user_data['inventory'] if i['name'] == item_name), None)
            
            if not inv_item:
                return jsonify({
                    "success": False,
                    "message": f"Item '{item_name}' not found"
                }), 404
            
            if inv_item['quantity'] < quantity:
                return jsonify({
                    "success": False,
                    "message": f"Insufficient stock for '{item_name}'"
                }), 400
            
            # Update inventory
            inv_item['quantity'] -= quantity
            
            # Add to order items
            item_total = quantity * inv_item['price']
            new_items.append({
                'name': item_name,
                'quantity': quantity,
                'price': inv_item['price']
            })
            total += item_total
        
        # Update order
        order['customer'] = customer
        order['items'] = new_items
        order['total'] = total
        order['date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Add to history
        user_data['history'].append({
            'action': 'Order Updated',
            'order_id': order['id'],
            'customer': customer,
            'date': order['date']
        })
        
        return jsonify({
            "success": True,
            "message": "Order updated successfully"
        })
        
    except Exception as e:
        print(f"Error updating order: {e}")
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/get_item/<int:id>')
@login_required
def get_item(id):
    user_email = session['user_email']
    user_data = users[user_email]
    
    item = next((item for item in user_data['inventory'] if item['id'] == id), None)
    if item:
        return jsonify(item)
    return jsonify({"error": "Item not found"}), 404

@app.route('/edit_item', methods=['POST'])
@login_required
def edit_item():
    try:
        user_email = session['user_email']
        user_data = init_user_if_needed(user_email)
        
        item_id = int(request.form['id'])
        item = next((item for item in user_data['inventory'] if item['id'] == item_id), None)
        if not item:
            return jsonify({"success": False, "message": "Item not found"}), 404
        
        item['name'] = request.form['name']
        item['category'] = request.form['category']
        item['quantity'] = int(request.form['quantity'])
        item['price'] = float(request.form['price'])
        item['expiry_date'] = request.form['expiry_date'] if request.form['expiry_date'] else None
        
        # Add to user's history
        user_data['history'].append({
            'action': 'Item Updated',
            'item': item['name'],
            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        return jsonify({"success": True, "message": "Item updated successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 400

@app.route('/delete_item/<int:id>', methods=['POST'])
@login_required
def delete_item(id):
    user_email = session['user_email']
    user_data = init_user_if_needed(user_email)
    
    item = next((item for item in user_data['inventory'] if item['id'] == id), None)
    if item:
        user_data['inventory'] = [i for i in user_data['inventory'] if i['id'] != id]
        
        # Add to user's history
        user_data['history'].append({
            'action': 'Item Deleted',
            'item': item['name'],
            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        return jsonify({"success": True, "message": "Item deleted successfully"})
    return jsonify({"success": False, "message": "Item not found"}), 404

@app.route('/stocks', methods=['GET', 'POST'])
@login_required
def stocks():
    user_email = session['user_email']
    user_data = init_user_if_needed(user_email)
    username = session['username']
    
    if request.method == 'POST':
        stock = {
            'symbol': request.form['symbol'],
            'quantity': int(request.form['quantity'])
        }
        users[user_email]['stocks'].append(stock)
    
    # Get user-specific data
    inventory_count = len(user_data['inventory'])
    total_sales = sum(order['total'] for order in user_data['orders'])
    low_stock_products = get_low_stock_products(user_email)
    
    return render_template('dashboard.html', 
                         inventory_count=inventory_count,
                         total_sales=total_sales,
                         company_name=user_data['company_name'],
                         low_stock_products=low_stock_products,
                         orders=user_data['orders'],
                         username=username)

if __name__ == '__main__':
    app.run(debug=True)

