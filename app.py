from flask import Flask, render_template, request, redirect, session, jsonify
from flask_mysqldb import MySQL
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = "secret"

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# -------- MYSQL CONFIG --------
app.config['MYSQL_HOST'] = os.environ.get("MYSQLHOST", "acela.proxy.rlwy.net")
app.config['MYSQL_USER'] = os.environ.get("MYSQLUSER", "root")
app.config['MYSQL_PASSWORD'] = os.environ.get("MYSQLPASSWORD", "vLPLByqJGClozdqOAoacAPPrjpjyYLjl")
app.config['MYSQL_DB'] = os.environ.get("MYSQLDATABASE", "railway")
app.config['MYSQL_PORT'] = int(os.environ.get("MYSQLPORT", 11649)) 

mysql = MySQL(app)

# -------- HELPER --------
def get_cart():
    cart = session.get("cart", {})

    # Fix old list cart
    if isinstance(cart, list):
        cart = {}
        session['cart'] = cart

    return cart

# -------- USER --------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/home')
def home():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM products")
    products = cur.fetchall()

    cart = get_cart()
    cart_count = sum(cart.values())

    return render_template("home.html", products=products, cart_count=cart_count)


@app.route("/categories")
def categories():
    cart = get_cart()
    cart_count = sum(cart.values())

    return render_template("categories.html", cart_count=cart_count)


@app.route("/category/<category_name>")
def category_page(category_name):
    cur = mysql.connection.cursor()

    query = "SELECT * FROM products WHERE LOWER(category) = LOWER(%s)"
    cur.execute(query, (category_name,))
    products = cur.fetchall()

    cart = get_cart()
    cart_count = sum(cart.values())

    return render_template(
        "category_products.html",
        products=products,
        category=category_name.capitalize(),
        cart_count=cart_count
    )


# -------- CART SYSTEM --------
@app.route('/add_to_cart/<int:id>')
def add_to_cart(id):

    # 🔥 ALWAYS start clean
    cart = session.get("cart", {})

    # 🔥 force dictionary (VERY IMPORTANT)
    if not isinstance(cart, dict):
        cart = {}

    id_str = str(id)

    # 🔥 safe increment
    cart[id_str] = cart.get(id_str, 0) + 1

    # 🔥 save back
    session["cart"] = cart
    session.modified = True

    # category redirect
    category = request.args.get('category')

    if category:
        return redirect(f'/category/{category}')
    else:
        return redirect('/home')


@app.route('/increase/<int:id>')
def increase(id):
    cart = get_cart()
    id = str(id)

    if id in cart:
        cart[id] += 1

    session['cart'] = cart
    return redirect('/cart')


@app.route('/decrease/<int:id>')
def decrease(id):
    cart = get_cart()
    id = str(id)

    if id in cart:
        cart[id] -= 1
        if cart[id] <= 0:
            del cart[id]

    session['cart'] = cart
    return redirect('/cart')


@app.route('/cart')
def cart():
    cart = get_cart()
    products = []
    total = 0

    if cart:
        ids = list(cart.keys())
        format_strings = ','.join(['%s'] * len(ids))

        cur = mysql.connection.cursor()
        cur.execute(f"SELECT * FROM products WHERE id IN ({format_strings})", tuple(ids))
        db_products = cur.fetchall()

        for p in db_products:
            pid = str(p[0])
            qty = cart.get(pid, 0)
            subtotal = p[2] * qty
            total += subtotal

            products.append({
                "id": p[0],
                "name": p[1],
                "price": p[2],
                "image": p[3],
                "qty": qty,
                "subtotal": subtotal
            })

    return render_template("cart.html", products=products, total=total)

@app.route('/checkout')
def checkout():

    if 'user_id' not in session:
        return redirect('/login_user')

    user_id = session['user_id']

    # Get cart from session
    cart = get_cart()

    products = []
    total = 0

    cur = mysql.connection.cursor()

    # User addresses
    cur.execute(
        "SELECT * FROM addresses WHERE user_id=%s",
        (user_id,)
    )
    addresses = cur.fetchall()

    # Cart products
    if cart:
        ids = list(cart.keys())
        format_strings = ','.join(['%s'] * len(ids))

        cur.execute(
            f"SELECT * FROM products WHERE id IN ({format_strings})",
            tuple(ids)
        )

        db_products = cur.fetchall()

        for p in db_products:
            pid = str(p[0])
            qty = cart.get(pid, 0)

            subtotal = p[2] * qty
            total += subtotal

            products.append({
                "id": p[0],
                "name": p[1],
                "price": p[2],
                "image": p[3],
                "qty": qty,
                "subtotal": subtotal
            })

    cur.close()

    return render_template(
        "checkout.html",
        addresses=addresses,
        products=products,
        total=total
    )
    
@app.route("/search")
def search_page():
    return render_template("search.html", active="search")

@app.route("/api/search")
def search_api():
    search = request.args.get("q", "")
    category = request.args.get("category", "all")

    cur = mysql.connection.cursor()

    query = "SELECT * FROM products WHERE 1=1"
    params = []

    # Category filter
    if category != "all":
        query += " AND LOWER(category) = LOWER(%s)"
        params.append(category)

    # Search filter
    if search:
        query += " AND LOWER(name) LIKE LOWER(%s)"
        params.append(f"%{search}%")

    query += " ORDER BY id DESC"

    cur.execute(query, tuple(params))
    products = cur.fetchall()
    cur.close()

    return jsonify(products)

# -------- ORDER --------
@app.route('/place_order', methods=['POST'])
def place_order():

    try:

        # LOGIN CHECK
        if 'user_id' not in session:
            return redirect('/login_user')

        # CART CHECK
        cart = get_cart()

        if not cart:
            return redirect('/cart')

        user_id = session['user_id']

        address_id = request.form.get('address_id')
        payment = request.form.get('payment')

        cur = mysql.connection.cursor()

        # GET ADDRESS DETAILS
        cur.execute("""

            SELECT
                name,
                phone,
                address

            FROM addresses

            WHERE id=%s
            AND user_id=%s

        """, (address_id, user_id))

        addr = cur.fetchone()

        if not addr:
            return "Invalid Address"

        # ADDRESS VALUES
        customer_name = addr[0]
        phone = addr[1]
        full_address = addr[2]

        # TOTAL
        total = 0

        for pid, qty in cart.items():

            cur.execute("SELECT * FROM products WHERE id=%s",(pid,))

            p = cur.fetchone()

            if p:
                total += float(p[2]) * int(qty)

        # INSERT ORDER
        cur.execute("""

            INSERT INTO orders
            (
                user_id,
                customer_name,
                address,
                total_amount,
                status,
                delivery_status,
                phone,
                payment_method
            )

            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)

        """, (

            user_id,
            customer_name,
            full_address,
            total,
            "Processing",
            "Pending",
            phone,
            payment

        ))

        mysql.connection.commit()

        # ORDER ID
        order_id = cur.lastrowid

        # INSERT ORDER ITEMS
        for pid, qty in cart.items():

            cur.execute(
                "SELECT * FROM products WHERE id=%s",
                (pid,)
            )

            p = cur.fetchone()

            if p:

                cur.execute("""

                    INSERT INTO order_items
                    (
                        order_id,
                        product_id,
                        product_name,
                        price,
                        quantity,
                        image
                    )

                    VALUES (%s,%s,%s,%s,%s,%s)

                """, (

                    order_id,
                    p[0],
                    p[1],
                    p[2],
                    qty,
                    p[3]

                ))

        mysql.connection.commit()

        # CLEAR CART
        session['cart'] = {}

        return redirect('/orders')

    except Exception as e:

        return f"PLACE ORDER ERROR : {str(e)}"

@app.route('/orders')
def orders():

    if 'user_id' not in session:
        return redirect('/login_user')

    user_id = session['user_id']

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT * FROM orders
        WHERE user_id = %s
        ORDER BY id DESC
    """, (user_id,))

    orders = cur.fetchall()

    order_data = []

    for o in orders:

        order_id = o[0]

        cur.execute("""
            SELECT * FROM order_items
            WHERE order_id = %s
        """, (order_id,))

        order_items = cur.fetchall()

        total_amount = 0

        for item in order_items:
            price = float(item[4] or 0)
            qty = int(item[5] or 0)
            total_amount += price * qty

        order_data.append({
            "order": o,
            "order_items": order_items,
            "total_amount": total_amount,
            "customer_name": o[2],
            "address": o[5]
        })

    cur.close()

    return render_template("orders.html", order_data=order_data)

@app.route('/order/<int:order_id>')
def order_details(order_id):

    if 'user_id' not in session:
        return redirect('/login_user')

    user_id = session['user_id']

    cur = mysql.connection.cursor()

    # 🔒 Check order belongs to user
    cur.execute("SELECT * FROM orders WHERE id=%s AND user_id=%s", (order_id, user_id))
    order = cur.fetchone()

    if not order:
        render_template("orders.html", error="Order not found")

    cur.execute("SELECT * FROM order_items WHERE order_id=%s", (order_id,))
    order_items = cur.fetchall()
    
    cur.close()

    return render_template("order_details.html", order=order, order_items=order_items)

@app.route('/cancel_order/<int:order_id>')
def cancel_order(order_id):

    if 'user_id' not in session:
        return redirect('/login_user')

    cur = mysql.connection.cursor()

    cur.execute("""
        UPDATE orders
        SET status = 'Cancelled'
        WHERE id = %s AND user_id = %s
    """, (order_id, session['user_id']))

    mysql.connection.commit()
    cur.close()

    return redirect('/orders')

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect('/login_user')

    return render_template(
        "profile.html",
        user_name=session.get('user_name'),
        user_email=session.get('user_email')
    )
    
@app.route('/delete_order/<int:order_id>')
def delete_order(order_id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM orders WHERE id=%s", (order_id,))
    mysql.connection.commit()
    cur.close()

    redirect('/orders')
    
@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO users(name,email,password) VALUES(%s,%s,%s)",
            (name, email, password)
        )
        mysql.connection.commit()

        return redirect('/login_user')

    return render_template('signup.html')

@app.route('/delivery_signup', methods=['GET', 'POST'])
def delivery_signup():

    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        area = request.form['area']
        password = request.form['password']

        cur = mysql.connection.cursor()

        cur.execute("""
            INSERT INTO delivery_users (name, phone, area, password, role)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, phone, area, password, "delivery"))

        mysql.connection.commit()

        # ✅ AUTO LOGIN
        delivery_id = cur.lastrowid
        session['delivery_id'] = delivery_id
        session['delivery_name'] = name

        return redirect('/delivery_home')

    return render_template('delivery_signup.html')

@app.route('/delivery_orders')
def delivery_orders():

    if 'delivery_id' not in session:
        return redirect('/delivery/login')

    cur = mysql.connection.cursor()

    cur.execute("""

        SELECT
            orders.id,
            orders.customer_name,
            orders.phone,
            order_items.product_name,
            order_items.quantity,
            orders.address,
            orders.total_amount,
            orders.delivery_status

        FROM orders

        JOIN order_items
        ON orders.id = order_items.order_id

        WHERE orders.status != 'Cancelled'

        ORDER BY orders.id DESC

    """)

    orders = cur.fetchall()

    cur.close()

    return render_template(
        "delivery_orders.html",
        orders=orders
    )

@app.route('/delivery_profile', methods=['GET', 'POST'])
def delivery_profile():

    if 'delivery_id' not in session:
        return redirect('/delivery/login')

    cur = mysql.connection.cursor()
    user_id = session['delivery_id']

    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        area = request.form['area']

        cur.execute("""
            UPDATE delivery_users 
            SET name=%s, phone=%s, area=%s
            WHERE id=%s
        """, (name, phone, area, user_id))

        mysql.connection.commit()

    cur.execute("SELECT * FROM delivery_users WHERE id=%s", (user_id,))
    user = cur.fetchone()

    return render_template("delivery_profile.html", user=user)

@app.route('/delivery/login', methods=['GET', 'POST'])
def delivery_login():

    if request.method == 'POST':
        phone = request.form['phone']
        password = request.form['password']

        cur = mysql.connection.cursor()

        cur.execute("""
            SELECT * FROM delivery_users 
            WHERE phone=%s AND password=%s
        """, (phone, password))

        user = cur.fetchone()

        if user:
            session['delivery_id'] = user[0]   # ✅ IMPORTANT FIX
            session['delivery_name'] = user[1]

            return redirect('/delivery_home')
        else:
            message = "❌ Invalid phone or password!"

    return render_template('login_user.html', message=message)

@app.route('/login_user', methods=['GET','POST'])
def login_user():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute(
            "SELECT * FROM users WHERE email=%s AND password=%s",
            (email, password)
        )
        user = cur.fetchone()

        if user:
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            session['user_email'] = user[2]

            return redirect('/home')
        
        else:
            message = "❌ Invalid email or password!"
            return render_template('login_user.html', message=message)
        
    return render_template('login_user.html')

@app.route('/logout_user')
def logout_user():
    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('user_email', None)

    return redirect('/login_user')

@app.route('/delivery_home')
def delivery_home():
    cur = mysql.connection.cursor()

    # Example queries (adjust to your DB)
    cur.execute("SELECT COUNT(*) FROM orders WHERE delivery_status='Assigned'")
    total_orders = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM orders WHERE delivery_status='Pending'")
    pending_orders = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM orders WHERE delivery_status='Cancelled'")
    cancelled_orders = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM orders WHERE delivery_status='Delivered'")
    delivered_orders = cur.fetchone()[0]

    cur.execute("SELECT * FROM orders WHERE delivery_status IN ('Assigned','Pending','Delivered')")
    orders = cur.fetchall()

    return render_template('delivery_home.html',total_orders=total_orders,pending_orders=pending_orders,delivered_orders=delivered_orders,orders=orders)
    
@app.route('/mark_delivered/<int:id>')
def mark_delivered(id):
    cur = mysql.connection.cursor()
    cur.execute("UPDATE orders SET delivery_status='Delivered' WHERE id=%s", (id,))
    mysql.connection.commit()
    return redirect('/delivery_home')

@app.route('/addresses', methods=['GET', 'POST'])
def addresses():
    if 'user_id' not in session:
        return redirect('/login_user')

    cur = mysql.connection.cursor()

    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        address = request.form['address']

        cur.execute("""
            INSERT INTO addresses (user_id, name, phone, address)
            VALUES (%s, %s, %s, %s)
        """, (session['user_id'], name, phone, address))

        mysql.connection.commit()
        return redirect('/addresses')

    cur.execute("SELECT * FROM addresses WHERE user_id=%s", (session['user_id'],))
    data = cur.fetchall()

    return render_template('addresses.html', addresses=data)

@app.route('/add_address', methods=['POST'])
def add_address():

    if 'user_id' not in session:
        return redirect('/login_user')

    name = request.form['name']
    phone = request.form['phone']
    address = request.form['full_address']
    lat = request.form['lat']
    lng = request.form['lng']

    cur = mysql.connection.cursor()

    cur.execute("""
    INSERT INTO addresses (user_id, name, phone, address, lat, lng)
    VALUES (%s,%s,%s,%s,%s,%s)
""", (session['user_id'], name, phone, address, lat, lng))

    mysql.connection.commit()

    return redirect('/checkout')

@app.route('/delete_address/<int:id>')
def delete_address(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM addresses WHERE id=%s", (id,))
    mysql.connection.commit()

    return redirect('/checkout')  # 🔥 come back to checkout

# -------- ADMIN --------
@app.route('/login', methods=['GET', 'POST'])
def login():

    # default empty message
    message = ""

    # when form submitted
    if request.method == 'POST':

        username = request.form.get('username')
        password = request.form.get('password')

        cur = mysql.connection.cursor()

        cur.execute("""
            SELECT * FROM admin
            WHERE username=%s AND password=%s
        """, (username, password))

        admin = cur.fetchone()

        cur.close()

        # SUCCESS LOGIN
        if admin:

            session['admin'] = admin[1]

            return redirect('/admin')

        # FAILED LOGIN
        else:

            message = "❌ Wrong Username or Password!"

            # IMPORTANT:
            # render SAME PAGE with message
            return render_template(
                'login_user.html',
                message=message
            )

    # normal page open
    return render_template(
        'login_user.html',
        message=message
    )

@app.route('/admin')
def admin():
    if 'admin' not in session:
        return redirect('/login_user')

    cur = mysql.connection.cursor()

    cur.execute("SELECT * FROM products")
    products = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM orders")
    orders = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM customers")
    customers = cur.fetchone()[0]

    cur.execute("SELECT SUM(total_amount) FROM orders")
    revenue = cur.fetchone()[0] or 0
    cur.close()

    return render_template('admin_dashboard.html',products=products,orders=orders,customers=customers,revenue=revenue)

@app.route('/add_product', methods=['POST'])
def add_product():
    if 'admin' not in session:
        return redirect('/login')

    name = request.form['name']
    price = request.form['price']
    category = request.form['category']

    image_file = request.files.get('image')

    image_url = ""

    if image_file and image_file.filename != "":
        # 🔥 Create folder if not exists
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])

        # 🔥 Safe + unique filename
        import time
        filename = str(int(time.time())) + "_" + secure_filename(image_file.filename)

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image_file.save(filepath)

        image_url = "/" + filepath  # store path

    # ✅ CORRECT DB INSERT
    cur = mysql.connection.cursor()
    cur.execute(
        "INSERT INTO products (name, price, category, image) VALUES (%s, %s, %s, %s)",
        (name, price, category, image_url)
    )
    mysql.connection.commit()
    cur.close()

    return redirect('/admin_products')

@app.route('/delete/<int:id>')
def delete(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM products WHERE id=%s", (id,))
    mysql.connection.commit()
    return redirect('/admin')

@app.route('/admin_orders')
def admin_orders():
    if 'admin' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT orders.id, users.name, orders.total_amount, orders.status
        FROM orders
        JOIN users ON orders.user_id = users.id
        ORDER BY orders.id DESC
    """)

    data = cur.fetchall()
    cur.close()

    return render_template("admin_orders.html", orders=data)

@app.route('/admin_products')
def admin_products():
    if 'admin' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM products")
    data = cur.fetchall()
    cur.close()

    return render_template("admin_products.html", products=data)

@app.route('/admin_customers')
def admin_customers():
    if 'admin' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users")
    data = cur.fetchall()
    cur.close()

    return render_template("admin_customers.html", customers=data)

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect('/login')

# -------- DEBUG --------
@app.route('/reset_cart')
def reset_cart():
    session.pop('cart', None)
    return "Cart reset done ✅"

# -------- RUN --------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)