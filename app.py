from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime
from scipy.optimize import linear_sum_assignment
import numpy as np

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Mock database for demonstration
users = {
    'donor@example.com': {
        'id': 1,
        'password': generate_password_hash('password'),
        'name': 'John Donor',
        'role': 'donor',
        'points': 100,
        'level': 2,
        'badges': ['First Donation', 'Regular Donor'],
        'donation_streak': 5,
        'total_donations': 15
    },
    'recipient@example.com': {
        'id': 2,
        'password': generate_password_hash('password'),
        'name': 'Jane Recipient',
        'role': 'recipient',
        'points': 75,
        'level': 1,
        'badges': ['Community Member'],
        'orders_completed': 8,
        'feedback_given': 6
    },
    'delivery@example.com': {
        'id': 3,
        'password': generate_password_hash('password'),
        'name': 'Dave Delivery',
        'role': 'delivery',
        'points': 150,
        'level': 3,
        'badges': ['Speed Demon', 'Reliable Driver'],
        'deliveries_completed': 15,
        'on_time_percentage': 98
    },
    'admin@example.com': {
        'id': 4,
        'password': generate_password_hash('password'),
        'name': 'Alice Admin',
        'role': 'admin'
    }
}

# Gamification system configuration
POINTS_SYSTEM = {
    'donor': {
        'make_donation': 10,
        'streak_bonus': 5,
        'quality_rating': 2,  # per star
        'milestone_bonus': 20  # every 10 donations
    },
    'recipient': {
        'complete_order': 5,
        'give_feedback': 3,
        'regular_user_bonus': 10  # monthly bonus for active users
    },
    'delivery': {
        'complete_delivery': 8,
        'on_time_bonus': 5,
        'perfect_rating': 10,
        'efficiency_bonus': 15  # for multiple deliveries in one route
    }
}

LEVEL_THRESHOLDS = {
    'donor': [0, 50, 100, 200, 500, 1000],
    'recipient': [0, 30, 80, 150, 300, 600],
    'delivery': [0, 40, 100, 200, 400, 800]
}

BADGES = {
    'donor': {
        'First Step': 'Made first donation',
        'Regular Donor': 'Made 5 donations',
        'Super Donor': 'Made 20 donations',
        'Consistency King': 'Maintained 10-day streak'
    },
    'recipient': {
        'Welcome': 'First order completed',
        'Active Member': 'Completed 5 orders',
        'Feedback Master': 'Gave feedback 10 times',
        'Community Pillar': 'Regular user for 3 months'
    },
    'delivery': {
        'First Mile': 'First delivery completed',
        'Speed Demon': '95% on-time deliveries',
        'Reliable Driver': 'Completed 50 deliveries',
        'Perfect Route': 'Multiple deliveries in one route'
    }
}

food_items = [
    {
        'id': 1,
        'name': 'Fresh Bread',
        'quantity': '10 loaves',
        'expiry': datetime(2025, 6, 30),
        'donor_id': 1,
        'status': 'available',
        'image': 'bread.jpg',
        'description': 'Freshly baked bread from our local bakery.',
        'location': '123 Main St, City'
    },
    {
        'id': 2,
        'name': 'Organic Vegetables',
        'quantity': '5 kg',
        'expiry': datetime(2025, 6, 25),
        'donor_id': 1,
        'status': 'assigned',
        'recipient_id': 2,
        'delivery_id': 3,
        'image': 'vegetables.jpg',
        'description': 'Mix of fresh organic vegetables including carrots, lettuce, and tomatoes.',
        'location': '123 Main St, City'
    },
    {
        'id': 3,
        'name': 'Canned Goods',
        'quantity': '20 cans',
        'expiry': datetime(2025, 12, 31),
        'donor_id': 1,
        'status': 'delivered',
        'recipient_id': 2,
        'delivery_id': 3,
        'image': 'canned.jpg',
        'description': 'Various canned goods including beans, corn, and soup.',
        'location': '123 Main St, City'
    }
]

delivery_routes = [
    {
        'id': 1,
        'food_item_id': 2,
        'delivery_agent_id': 3,
        'status': 'in_progress',
        'pickup_location': '123 Main St, City',
        'delivery_location': '456 Oak Ave, City',
        'estimated_delivery': datetime(2025, 6, 24, 14, 0),
        'actual_delivery': None
    }
]

class User(UserMixin):
    def __init__(self, id, email, name, role):
        self.id = id
        self.email = email
        self.name = name
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    for email, user_data in users.items():
        if user_data['id'] == int(user_id):
            return User(user_data['id'], email, user_data['name'], user_data['role'])
    return None

def award_points(user_email, action_type):
    if user_email not in users:
        return
    
    user = users[user_email]
    role = user['role']
    
    if role not in POINTS_SYSTEM:
        return
    
    points = POINTS_SYSTEM[role].get(action_type, 0)
    user['points'] = user.get('points', 0) + points
    
    # Check for level up
    current_level = user.get('level', 1)
    thresholds = LEVEL_THRESHOLDS[role]
    
    for level, threshold in enumerate(thresholds, 1):
        if user['points'] >= threshold and level > current_level:
            user['level'] = level
            flash(f'Congratulations! You\'ve reached level {level}!')
            
    # Check for new badges
    check_and_award_badges(user_email)

def check_and_award_badges(user_email):
    user = users[user_email]
    role = user['role']
    
    if role not in BADGES:
        return
    
    current_badges = user.get('badges', [])
    
    for badge_name, requirement in BADGES[role].items():
        if badge_name not in current_badges:
            # Check if badge requirements are met
            badge_earned = False
            
            if role == 'donor':
                total_donations = user.get('total_donations', 0)
                streak = user.get('donation_streak', 0)
                
                if badge_name == 'First Step' and total_donations >= 1:
                    badge_earned = True
                elif badge_name == 'Regular Donor' and total_donations >= 5:
                    badge_earned = True
                elif badge_name == 'Super Donor' and total_donations >= 20:
                    badge_earned = True
                elif badge_name == 'Consistency King' and streak >= 10:
                    badge_earned = True
            
            elif role == 'recipient':
                orders = user.get('orders_completed', 0)
                feedback = user.get('feedback_given', 0)
                
                if badge_name == 'Welcome' and orders >= 1:
                    badge_earned = True
                elif badge_name == 'Active Member' and orders >= 5:
                    badge_earned = True
                elif badge_name == 'Feedback Master' and feedback >= 10:
                    badge_earned = True
            
            elif role == 'delivery':
                deliveries = user.get('deliveries_completed', 0)
                on_time = user.get('on_time_percentage', 0)
                
                if badge_name == 'First Mile' and deliveries >= 1:
                    badge_earned = True
                elif badge_name == 'Speed Demon' and on_time >= 95:
                    badge_earned = True
                elif badge_name == 'Reliable Driver' and deliveries >= 50:
                    badge_earned = True
            
            if badge_earned:
                if 'badges' not in user:
                    user['badges'] = []
                user['badges'].append(badge_name)
                flash(f'Congratulations! You\'ve earned the {badge_name} badge!')
                award_points(user_email, 'badge_earned')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        role = request.form.get('role')
        
        if email in users:
            flash('Email already registered. Please login or use a different email.')
            return redirect(url_for('signup'))
        
        # Create new user with initial gamification stats
        new_user_id = max(user['id'] for user in users.values()) + 1
        users[email] = {
            'id': new_user_id,
            'password': generate_password_hash(password),
            'name': name,
            'role': role,
            'points': 0,
            'level': 1,
            'badges': [],
            'total_donations': 0,
            'donation_streak': 0,
            'orders_completed': 0,
            'feedback_given': 0,
            'deliveries_completed': 0,
            'on_time_percentage': 100
        }
        
        # Log in the new user
        user = User(new_user_id, email, name, role)
        login_user(user)
        
        flash(f'Welcome to Food Buddy! You\'ve joined as a {role}. Start earning points and badges!')
        
        # Redirect based on role
        if role == 'donor':
            return redirect(url_for('donor_dashboard'))
        elif role == 'recipient':
            return redirect(url_for('recipient_dashboard'))
        elif role == 'delivery':
            return redirect(url_for('delivery_dashboard'))
        elif role == 'admin':
            return redirect(url_for('admin_dashboard'))
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if email not in users:
            flash('Email not found. Please check your email or register.')
            return redirect(url_for('login'))
        
        user_data = users[email]
        if check_password_hash(user_data['password'], password):
            user = User(user_data['id'], email, user_data['name'], user_data['role'])
            login_user(user)
            
            # Redirect based on role
            if user.role == 'donor':
                return redirect(url_for('donor_dashboard'))
            elif user.role == 'recipient':
                return redirect(url_for('recipient_dashboard'))
            elif user.role == 'delivery':
                return redirect(url_for('delivery_dashboard'))
            elif user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
        else:
            flash('Incorrect password. Please try again.')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard/donor')
@login_required
def donor_dashboard():
    if current_user.role != 'donor':
        flash('Access denied: You do not have permission to view this page.')
        return redirect(url_for('login'))
    
    user_data = users[next(email for email, data in users.items() if data['id'] == current_user.id)]
    donor_items = [item for item in food_items if item['donor_id'] == current_user.id]
    
    stats = {
        'available': sum(1 for item in donor_items if item['status'] == 'available'),
        'assigned': sum(1 for item in donor_items if item['status'] == 'assigned'),
        'delivered': sum(1 for item in donor_items if item['status'] == 'delivered'),
        'total': len(donor_items),
        'points': user_data.get('points', 0),
        'level': user_data.get('level', 1),
        'badges': user_data.get('badges', []),
        'streak': user_data.get('donation_streak', 0)
    }
    
    return render_template('donor_dashboard.html', 
                         user=current_user,
                         food_items=donor_items,
                         stats=stats)

@app.route('/dashboard/recipient')
@login_required
def recipient_dashboard():
    if current_user.role != 'recipient':
        flash('Access denied: You do not have permission to view this page.')
        return redirect(url_for('login'))
    
    user_data = users[next(email for email, data in users.items() if data['id'] == current_user.id)]
    available_items = [item for item in food_items if item['status'] == 'available']
    assigned_items = [item for item in food_items if item.get('recipient_id') == current_user.id and item['status'] in ['assigned', 'in_delivery']]
    received_items = [item for item in food_items if item.get('recipient_id') == current_user.id and item['status'] == 'delivered']
    
    stats = {
        'available': len(available_items),
        'assigned': len(assigned_items),
        'received': len(received_items),
        'points': user_data.get('points', 0),
        'level': user_data.get('level', 1),
        'badges': user_data.get('badges', []),
        'orders_completed': user_data.get('orders_completed', 0)
    }
    
    return render_template('recipient_dashboard.html',
                         user=current_user,
                         available_items=available_items,
                         assigned_items=assigned_items,
                         received_items=received_items,
                         stats=stats)

@app.route('/dashboard/delivery')
@login_required
def delivery_dashboard():
    if current_user.role != 'delivery':
        flash('Access denied: You do not have permission to view this page.')
        return redirect(url_for('login'))
    
    user_data = users[next(email for email, data in users.items() if data['id'] == current_user.id)]
    my_routes = [route for route in delivery_routes if route['delivery_agent_id'] == current_user.id]
    
    delivery_items = []
    for route in my_routes:
        for item in food_items:
            if item['id'] == route['food_item_id']:
                delivery_items.append({
                    'item': item,
                    'route': route
                })
    
    stats = {
        'pending': sum(1 for item in delivery_items if item['route']['status'] == 'pending'),
        'in_progress': sum(1 for item in delivery_items if item['route']['status'] == 'in_progress'),
        'completed': sum(1 for item in delivery_items if item['route']['status'] == 'completed'),
        'total': len(delivery_items),
        'points': user_data.get('points', 0),
        'level': user_data.get('level', 1),
        'badges': user_data.get('badges', []),
        'on_time_percentage': user_data.get('on_time_percentage', 100)
    }
    
    return render_template('delivery_dashboard.html',
                         user=current_user,
                         delivery_items=delivery_items,
                         stats=stats)

@app.route('/dashboard/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Access denied: You do not have permission to view this page.')
        return redirect(url_for('login'))
    
    user_counts = {
        'donors': sum(1 for user in users.values() if user['role'] == 'donor'),
        'recipients': sum(1 for user in users.values() if user['role'] == 'recipient'),
        'delivery_agents': sum(1 for user in users.values() if user['role'] == 'delivery'),
        'admins': sum(1 for user in users.values() if user['role'] == 'admin')
    }
    
    food_stats = {
        'available': sum(1 for item in food_items if item['status'] == 'available'),
        'assigned': sum(1 for item in food_items if item['status'] == 'assigned'),
        'delivered': sum(1 for item in food_items if item['status'] == 'delivered'),
        'total': len(food_items)
    }
    
    return render_template('admin_dashboard.html',
                         user=current_user,
                         food_items=food_items,
                         users=users,
                         user_counts=user_counts,
                         food_stats=food_stats)
# hungarin algo
def run_hungarian_matching():
    # Filter available items and recipients
    available_items = [item for item in food_items if item['status'] == 'available']
    recipients = [user for user in users.values() if user['role'] == 'recipient']

    if not available_items or not recipients:
        return

    # Define cost matrix: rows = items, cols = recipients
    # Here, we use a dummy cost: distance can be implemented later
    cost_matrix = np.zeros((len(available_items), len(recipients)))

    for i, item in enumerate(available_items):
        for j, recipient in enumerate(recipients):
            # Dummy cost: you can use real distance, freshness, quantity logic here
            cost_matrix[i][j] = abs(item['id'] - recipient['id'])  # Just a placeholder

    # Run Hungarian algorithm
    row_ind, col_ind = linear_sum_assignment(cost_matrix)

    # Assign matches
    for i, j in zip(row_ind, col_ind):
        item = available_items[i]
        recipient = recipients[j]
        item['status'] = 'assigned'
        item['recipient_id'] = recipient['id']

        # You can also log, notify, or trigger delivery here
        print(f"Assigned Item {item['name']} to Recipient {recipient['name']}")
@app.route('/run_matching')
@login_required
def run_matching():
    if current_user.role not in ['admin', 'recipient']:
        flash('Access denied: Only admins can run matching.')
        return redirect(url_for('login'))
    run_hungarian_matching()
    flash('Hungarian matching complete. Check assigned items.')
    return redirect(url_for('recipient_dashboard'))

if __name__ == '__main__':
    app.run(debug=True)