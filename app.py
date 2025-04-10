import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
DATABASE = 'database/usersnew.db'


if not os.path.exists('database'):
    os.makedirs('database')

def get_db():
    """Establish and return a database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database with required tables."""
    with get_db() as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                is_admin INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                status TEXT DEFAULT 'Placed',
                delivery_date TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                comment TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        ''')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handles user registration."""
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        with get_db() as db:
            try:
                db.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', 
                           (name, email, password))
                db.commit()
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash('Username or email already exists.', 'danger')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        with get_db() as db:
            user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['is_admin'] = user['is_admin']
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    """User dashboard."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', username=session['username'])

@app.route('/logout')
def logout():
    """Handle user logout."""
    session.clear()
    return redirect(url_for('index'))

# --- Admin Routes ---

@app.route('/admin_login')
def admin_login():
    return render_template('admin_login.html')

@app.route('/admin_login_action', methods=['GET', 'POST'])
def admin_login_action():
    """Admin login."""
    # if 'admin_id' in session:
    #     return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        email = request.form['admin_email']
        password = request.form['admin_password']

        con = sqlite3.connect('database/usersnew.db')
        c = con.cursor()
        c.execute("SELECT * FROM users WHERE email = ? AND is_admin = ?",(email,1))
        data = c.fetchone()
        if data:
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('admin_login'))
    else:
        return redirect(url_for('admin_login'))
    
    

@app.route('/admin_dashboard')
def admin_dashboard():
    """Admin dashboard to manage orders and feedback."""
    # if not session.get('admin_id'):
    #     return redirect(url_for('admin_login'))

    # with get_db() as db:
    #     orders = db.execute('SELECT * FROM orders').fetchall()
    #     feedbacks = db.execute('SELECT * FROM feedback').fetchall()

    # return render_template('admin_dashboard.html', 
    #                        admin_name=session['admin_name'], 
    #                        orders=orders, 
    #                        feedbacks=feedbacks)
    return render_template('admin_dashboard.html')

# --- Product & Cart Routes ---
@app.route('/catalog')
def catalog():
    """Render the product catalog page."""
    return render_template('catalog.html')

@app.route('/cart')
def cart():
    """Render the shopping cart page."""
    return render_template('cart.html')


orders = [
    {"id": 101, "name": "Fresh Vegetables", "price": 5.99, "status": "Delivered", "date": "March 25, 2025"},
    {"id": 102, "name": "Dairy Products", "price": 2.99, "status": "Out for Delivery", "date": "March 27, 2025"},
    {"id": 103, "name": "Grains & Cereals", "price": 4.99, "status": "Processing", "date": "March 28, 2025"}
]

@app.route('/orders')
def orders_page():
    return render_template('orders.html', orders=orders)

@app.route('/feedback')
def feedback_page():
    """Render the feedback page."""
    return render_template('feedback.html')

# --- API Routes ---
@app.route('/api/products', methods=['GET'])
def get_products():
    """Return a list of available products from the database."""
    with get_db() as db:
        products = db.execute('SELECT * FROM products').fetchall()
    return jsonify([dict(product) for product in products])

@app.route('/api/cart', methods=['POST'])
def add_to_cart():
    """Add an item to the user's cart (session-based)."""
    product_name = request.json.get("product_name")
    
    if "cart" not in session:
        session["cart"] = []

    session["cart"].append(product_name)
    session.modified = True  
    return jsonify({"message": f"{product_name} added to cart", "cart": session["cart"]})

@app.route('/api/cart', methods=['GET'])
def get_cart():
    """Retrieve the user's cart."""
    return jsonify(session.get("cart", []))

@app.route('/api/orders', methods=['POST'])
def place_order():
    """Process an order from the user's cart."""
    if "cart" not in session or not session["cart"]:
        return jsonify({"message": "Your cart is empty!"}), 400

    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"message": "User not logged in!"}), 401

    with get_db() as db:
        db.execute("INSERT INTO orders (user_id, status) VALUES (?, 'Processing')", (user_id,))
        db.commit()

    session["cart"] = []  
    return jsonify({"message": "Order placed successfully!"})

@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    """Receive user feedback."""
    feedback_text = request.json.get("feedback")
    user_id = session.get('user_id')

    if not user_id or not feedback_text:
        return jsonify({"message": "Invalid input!"}), 400

    with get_db() as db:
        db.execute("INSERT INTO feedback (user_id, comment) VALUES (?, ?)", (user_id, feedback_text))
        db.commit()

    return jsonify({"message": "Feedback submitted!"})

if __name__ == '__main__':
    init_db()  
    app.run(debug=True)
