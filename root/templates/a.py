from flask import Flask, render_template, request, redirect, session
from flask_mysqldb import MySQL

app = Flask(__name__)
app.secret_key = "secret123"

# MySQL Config
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'your_database_name'

mysql = MySQL(app)

# ================================
# ✅ DELIVERY SIGNUP (AUTO LOGIN)
# ================================
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


# ================================
# ✅ DELIVERY LOGIN
# ================================
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
            session['delivery_id'] = user[0]
            session['delivery_name'] = user[1]

            return redirect('/delivery_home')
        else:
            return "Invalid Login"

    return render_template('delivery_login.html')


# ================================
# ✅ DELIVERY DASHBOARD
# ================================
@app.route('/delivery_home')
def delivery_home():

    if 'delivery_id' not in session:
        return redirect('/delivery/login')

    cur = mysql.connection.cursor()

    cur.execute("SELECT COUNT(*) FROM orders")
    total_orders = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM orders WHERE delivery_status='Pending'")
    pending_orders = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM orders WHERE delivery_status='Delivered'")
    delivered_orders = cur.fetchone()[0]

    cur.execute("SELECT * FROM orders")
    orders = cur.fetchall()

    return render_template('delivery_home.html',
                           total_orders=total_orders,
                           pending_orders=pending_orders,
                           delivered_orders=delivered_orders,
                           orders=orders)


# ================================
# ✅ DELIVERY ORDERS PAGE
# ================================
@app.route('/delivery_orders')
def delivery_orders():

    if 'delivery_id' not in session:
        return redirect('/delivery/login')

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM orders")
    orders = cur.fetchall()

    return render_template('delivery_orders.html', orders=orders)


# ================================
# ✅ MARK AS DELIVERED
# ================================
@app.route('/mark_delivered/<int:id>')
def mark_delivered(id):

    if 'delivery_id' not in session:
        return redirect('/delivery/login')

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE orders 
        SET delivery_status='Delivered' 
        WHERE id=%s
    """, (id,))

    mysql.connection.commit()

    return redirect('/delivery_home')


# ================================
# ✅ DELIVERY PROFILE
# ================================
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

    return render_template('delivery_profile.html', user=user)


# ================================
# ✅ LOGOUT
# ================================
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/delivery/login')


# ================================
# RUN
# ================================
if __name__ == '__main__':
    app.run(debug=True)