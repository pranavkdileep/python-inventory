from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import random

class SalesPrediction:
    def __init__(self):
        self.model = LinearRegression()
        self.is_trained = False
        self.first_date = None
    
    def prepare_data(self, orders):
        """Prepare historical sales data from orders"""
        daily_sales = {}
        
        for order in orders:
            date = datetime.strptime(order['date'], "%Y-%m-%d %H:%M:%S").date()
            if date not in daily_sales:
                daily_sales[date] = 0
            daily_sales[date] += float(order.get('total', 0))
        
        # Sort by date
        sorted_dates = sorted(daily_sales.keys())
        
        if len(sorted_dates) < 5:  # Need minimum data points
            return None, None
        
        self.first_date = sorted_dates[0]
        
        # Convert to arrays
        X = np.array([(date - self.first_date).days for date in sorted_dates]).reshape(-1, 1)
        y = np.array([daily_sales[date] for date in sorted_dates])
        
        return X, y
    
    def train(self, orders):
        """Train the model with historical order data"""
        X, y = self.prepare_data(orders)
        
        if X is None or y is None:
            self.is_trained = False
            return False
        
        self.model.fit(X, y)
        self.is_trained = True
        return True
    
    def predict_future_sales(self, orders, days_to_predict=30):
        """Predict sales for the next specified number of days"""
        if not self.is_trained or self.first_date is None:
            return None, None, None
        
        # Generate future dates
        last_date = datetime.now().date()
        future_dates = [last_date + timedelta(days=x+1) for x in range(days_to_predict)]
        
        # Prepare prediction input
        future_X = np.array([(date - self.first_date).days for date in future_dates]).reshape(-1, 1)
        
        # Make predictions
        predictions = self.model.predict(future_X)
        predictions = [max(0, p) for p in predictions]  # Ensure no negative predictions
        
        # Calculate confidence (R² score)
        confidence = self.model.score(*self.prepare_data(orders))
        
        return future_dates, predictions, confidence
    
    def get_prediction_data(self, orders):
        """Get formatted prediction data for the frontend"""
        # Train model
        if not self.train(orders):
            return {
                'labels': [],
                'data': [],
                'confidence': 0,
                'error': 'Insufficient data (minimum 5 days required)'
            }
        
        # Make predictions
        future_dates, predictions, confidence = self.predict_future_sales(orders)
        
        if not future_dates:
            return {
                'labels': [],
                'data': [],
                'confidence': 0,
                'error': 'Prediction failed'
            }
        
        return {
            'labels': [date.strftime("%Y-%m-%d") for date in future_dates],
            'data': [round(pred, 2) for pred in predictions],
            'confidence': confidence,
            'error': None
        }

    def test_with_sample_data(self):
        """Test the prediction model with sample data"""
        sample_orders = generate_sample_data()
        prediction_data = self.get_prediction_data(sample_orders)
        return prediction_data, sample_orders

def get_sales_insights(orders):
    """Get additional sales insights"""
    if not orders:
        return {
            'trend': 'neutral',
            'avg_daily_sales': 0,
            'peak_day': None,
            'peak_amount': 0
        }
    
    daily_sales = {}
    for order in orders:
        date = datetime.strptime(order['date'], "%Y-%m-%d %H:%M:%S").date()
        if date not in daily_sales:
            daily_sales[date] = 0
        daily_sales[date] += float(order.get('total', 0))
    
    if not daily_sales:
        return {
            'trend': 'neutral',
            'avg_daily_sales': 0,
            'peak_day': None,
            'peak_amount': 0
        }
    
    # Calculate insights
    peak_day = max(daily_sales.items(), key=lambda x: x[1])
    avg_daily_sales = sum(daily_sales.values()) / len(daily_sales)
    
    # Determine trend
    dates = sorted(daily_sales.keys())
    if len(dates) >= 2:
        recent_avg = daily_sales[dates[-1]]
        if len(dates) >= 7:
            recent_avg = sum(daily_sales[date] for date in dates[-7:]) / 7
        old_avg = daily_sales[dates[0]]
        if len(dates) >= 7:
            old_avg = sum(daily_sales[date] for date in dates[:7]) / 7
        
        trend = 'up' if recent_avg > old_avg else 'down' if recent_avg < old_avg else 'neutral'
    else:
        trend = 'neutral'
    
    return {
        'trend': trend,
        'avg_daily_sales': round(avg_daily_sales, 2),
        'peak_day': peak_day[0].strftime("%Y-%m-%d"),
        'peak_amount': round(peak_day[1], 2)
    }

def generate_sample_data():
    """Generate sample sales data for testing the ML model"""
    # Start date will be 60 days ago
    start_date = datetime.now() - timedelta(days=60)
    
    # Generate sample orders
    sample_orders = []
    
    # Create some sample products
    products = [
        {"name": "Product A", "price": 499.99},
        {"name": "Product B", "price": 299.99},
        {"name": "Product C", "price": 999.99},
        {"name": "Product D", "price": 149.99},
        {"name": "Product E", "price": 749.99}
    ]
    
    # Generate orders with a realistic pattern
    for day in range(60):
        current_date = start_date + timedelta(days=day)
        
        # Generate more orders for weekends
        is_weekend = current_date.weekday() >= 5
        num_orders = random.randint(3, 8) if is_weekend else random.randint(1, 5)
        
        # Add some seasonality (more sales in the middle of the month)
        if 10 <= current_date.day <= 20:
            num_orders += random.randint(1, 3)
        
        for _ in range(num_orders):
            # Create order
            order_items = []
            order_total = 0
            
            # Add 1-3 products to each order
            for _ in range(random.randint(1, 3)):
                product = random.choice(products)
                quantity = random.randint(1, 3)
                item_total = product['price'] * quantity
                
                order_items.append({
                    'name': product['name'],
                    'quantity': quantity,
                    'price': product['price'],
                    'total': item_total
                })
                order_total += item_total
            
            # Add some random hours to the date
            order_time = current_date + timedelta(hours=random.randint(9, 20))
            
            order = {
                'date': order_time.strftime("%Y-%m-%d %H:%M:%S"),
                'items': order_items,
                'total': order_total,
                'customer': f"Customer{random.randint(1, 100)}"
            }
            
            sample_orders.append(order)
    
    return sample_orders 