
from flask import Flask, request, jsonify
import sqlite3
from datetime import datetime
from flask_cors import CORS
import random
app = Flask(__name__)
CORS(app, origins=["https://astonishing-bunny-deb24c.netlify.app"])

# Функция для подключения к базе данных
def get_db_connection():
    conn = sqlite3.connect('lumina.db')
    conn.row_factory = sqlite3.Row
    return conn

# Инициализация таблиц
with get_db_connection() as conn:  
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            referrer_id INTEGER,
            referrals_count INTEGER,
            balance REAL DEFAULT 0,
            registration_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            user_theme TEXT DEFAULT 'light'
        );
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS wallets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            wallet_currency TEXT,
            wallet_address TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
        );
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS tradings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            ai_model TEXT,
            start_balance REAL,
            result_percent REAL,
            result_value REAL,
            date DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
        );
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            transaction_type TEXT,
            amount REAL,
            date DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
        );
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS bonuses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            value REAL,
            description TEXT,
            day integer DEFAULT 1,
            getting_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
        );
    ''')
    conn.execute('''
    CREATE TABLE IF NOT EXISTS participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT NOT NULL,
        views INTEGER DEFAULT 0,
        received INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    );
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_views ON participants (views DESC);')
    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions (date);
    ''')

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    return response

# Предварительный запрос для CORS
@app.route('/users<int:user_id>', methods=['OPTIONS'])
def options_users():
    return '', 200
# Users API
@app.route('/users/<int:user_id>', methods=['POST'])
def create_or_update_user(user_id):
    data = request.get_json()
    username = data.get('username')
    first_name = data.get('first_name')
    last_name = data.get('last_name')

    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Проверяем, существует ли пользователь
    user = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()

    if user:
        # Обновляем существующего пользователя
        cursor.execute('''
            UPDATE users
            SET username = ?, first_name = ?, last_name = ?
            WHERE user_id = ?
        ''', (username, first_name, last_name, user_id))
    else:
        # Создаем нового пользователя
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
        ''', (user_id, username, first_name, last_name))

    conn.commit()
    conn.close()

    return jsonify({'message': 'User profile created/updated successfully'}), 201

@app.route('/users/<int:user_id>', methods=['PUT'])
def update_user_theme(user_id):
    try:
        # Получаем данные из запроса
        data = request.get_json()
        new_theme = data.get('user_theme')

        # Проверяем наличие обязательного поля
        if not new_theme or new_theme not in ['light', 'dark']:
            return jsonify({"error": "Invalid theme value. Must be 'light' or 'dark'"}), 400

        # Подключаемся к базе данных
        conn = get_db_connection()
        cursor = conn.cursor()

        # Обновляем тему пользователя
        cursor.execute(
            "UPDATE users SET user_theme = ? WHERE user_id = ?",
            (new_theme, user_id)
        )

        # Проверяем, был ли обновлен хотя бы 1 ряд
        if cursor.rowcount == 0:
            return jsonify({"error": "User not found"}), 404
        
        conn.commit()  # Сохраняем изменения
        conn.close()
        return jsonify({"message": "Theme updated successfully", "user_theme": new_theme}), 200

    except sqlite3.Error as e:
        print(e)
        return jsonify({"error": f"Database error: {str(e)}"}), 500
        
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if conn:
            conn.close()

@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
    conn.close()
    if user is None:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(dict(user))

# Transactions API
@app.route('/transactions/<int:user_id>', methods=['GET'])
def get_transactions(user_id):
    conn = get_db_connection()
    transactions = conn.execute(
        'SELECT * FROM transactions WHERE user_id = ? ORDER BY date DESC', 
        (user_id,)
    ).fetchall()
    conn.close()
    return jsonify([dict(tx) for tx in transactions])
@app.route('/transactions/<int:user_id>', methods=['POST'])
def create_transaction(user_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body is empty or not JSON"}), 400

    amount = data.get('amount')
    transaction_type = data.get('transaction_type')
    
    if amount is None or transaction_type is None:
        return jsonify({"error": "Missing required fields: 'amount' and 'transaction_type'"}), 400
    
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO transactions (user_id, amount, transaction_type) VALUES (?, ?, ?)', (user_id, amount, transaction_type))
        conn.commit()
        return jsonify({"message": "Transaction created successfully", "user_id": user_id, "amount": amount, "transaction_type": transaction_type}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
# Wallets API
@app.route('/wallets/<int:user_id>', methods=['GET'])
def get_wallets(user_id):
    conn = get_db_connection()
    wallets = conn.execute('SELECT * FROM wallets WHERE user_id = ?', (user_id,)).fetchall()
    conn.close()
    return jsonify([dict(wallet) for wallet in wallets])

@app.route('/wallets/<int:user_id>', methods=['POST'])
def create_wallet(user_id):
    data = request.get_json()
    currency = data.get('wallet_currency')
    address = data.get('wallet_address')
    if not currency or not address:
        return jsonify({'error': 'Currency and address are required'}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO wallets (user_id, wallet_currency, wallet_address) VALUES (?, ?, ?)', (user_id, currency, address))
    conn.commit()
    wallet_id = cursor.lastrowid
    conn.close()
    return jsonify({'id': wallet_id, 'currency': currency, 'address': address}), 201

@app.route('/wallets/<int:user_id>/<int:wallet_id>', methods=['PUT'])
def update_wallet(user_id, wallet_id):
    data = request.get_json()
    currency = data.get('wallet_currency')
    address = data.get('wallet_address')
    if not currency or not address:
        return jsonify({'error': 'Currency and address are required'}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE wallets SET wallet_currency = ?, wallet_address = ? WHERE user_id = ? AND id = ?', (currency, address, user_id, wallet_id))
    conn.commit()
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({'error': 'Wallet not found'}), 404
    conn.close()
    return jsonify({'id': wallet_id, 'currency': currency, 'address': address})

@app.route('/wallets/<int:user_id>/<int:wallet_id>', methods=['DELETE'])
def delete_wallet(user_id, wallet_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM wallets WHERE user_id = ? AND id = ?', (user_id, wallet_id))
    conn.commit()
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({'error': 'Wallet not found'}), 404
    conn.close()
    return jsonify({'success': True})

# Trading API
@app.route('/tradings/<int:user_id>', methods=['GET'])
def get_tradings(user_id):
    conn = get_db_connection()
    tradings = conn.execute('SELECT * FROM tradings WHERE user_id = ?', (user_id,)).fetchall()
    conn.close()
    return jsonify([dict(trading) for trading in tradings])
@app.route('/gettrade/<string:ai_model>/<int:user_id>', methods=['GET'])
def get_trade(ai_model, user_id):
    if not ai_model:
        return jsonify({"error": "ai_model parameter is required"}), 400
    conn = get_db_connection()
    ai_model = ai_model[1:]
    print(ai_model)
    cursor = conn.cursor()
    start_balance = float(cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,)).fetchone()[0])
    conn.close()
    if ai_model in ['Stable','v2core']:
        print(121231121312)
        delay = random.randint(13,20)
        sign = random.choice([-1,1,1])
        result_percent = round(sign*random.uniform(0,2),2)
        result_value = round(start_balance*result_percent/100,2)
    elif ai_model in ['Neutral', 'v2opt']:
        delay = random.randint(7,13)
        sign = random.choice([-1,-1,-1,-1,1,1,1,1,1])
        result_percent = round(sign*random.uniform(1.5,5),2)
        result_value = round(start_balance*result_percent/100,2)
    else:
        delay = random.randint(3,7)
        sign = random.choice([-1,-1,1])
        result_percent = round(sign*random.uniform(4.5,10),2)
        result_value = round(start_balance*result_percent/100,2)
    
    delay *= 1000
    
    print(result_percent,result_value)
    response_data = {
        "result_value": result_value,
        "result_percent": result_percent,
        "ai_model": ai_model,
        "delay": delay
    }
    print(response_data)
    return jsonify(response_data)
@app.route('/tradings/<int:user_id>', methods=['POST'])
def create_trading(user_id):
    data = request.get_json()
    ai_model = data.get('ai_model')
    result_percent = data.get('result_percent')
    start_balance = data.get('start_balance')
    result_value = data.get('result_value')
    if not ai_model or result_percent is None:
        return jsonify({'error': 'AI model and result percent are required'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO tradings (user_id, ai_model, start_balance, result_percent, result_value) VALUES (?, ?, ?, ?, ?)',
                   (user_id, ai_model, start_balance, result_percent, result_value))
    cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (round(start_balance+result_value,2), user_id))
    conn.commit()
    trading_id = cursor.lastrowid
    conn.close()
    return jsonify({
        'id': trading_id,
        'ai_model': ai_model,
        'start_balance': start_balance,
        'result_percent': result_percent,
        'result_value': result_value,
        'date': datetime.now().isoformat()
    }), 201

# Bonuses API
@app.route('/bonuses/<int:user_id>', methods=['GET'])
def get_bonuses(user_id):
    conn = get_db_connection()
    bonuses = conn.execute('SELECT * FROM bonuses WHERE user_id = ?', (user_id,)).fetchall()
    conn.close()
    return jsonify([dict(bonus) for bonus in bonuses])

# Реферальный бонус
@app.route('/bonuses/<int:user_id>/referral', methods=['POST'])
def claim_referral_bonus(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Получаем количество рефералов пользователя
        cursor.execute("SELECT referrals_count FROM users WHERE user_id = ?", (user_id,))
        referrals = cursor.fetchone()
        
        if not referrals or referrals[0] == 0:
            return jsonify({"error": "No referrals available"}), 400
        
        # Рассчитываем бонус (10 единиц на каждого реферала)
        bonus_value = referrals[0] * 10.0
        
        # Сохраняем в базу
        cursor.execute(
            "INSERT INTO bonuses (user_id, value, description) VALUES (?, ?, ?)",
            (user_id, bonus_value, "Referral bonus")
        )
        conn.commit()
        cursor.execute("UPDATE users  SET balance = balance+? WHERE user_id = ?;", (bonus_value,user_id))
        conn.commit()
        
        return jsonify({
            "success": True,
            "bonus": bonus_value,
            "message": "Referral bonus claimed successfully"
        }), 201

    except sqlite3.Error as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()

# Бонус за регистрацию
@app.route('/bonuses/<int:user_id>/registration', methods=['POST'])
def claim_registration_bonus(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Проверяем, не был ли уже получен бонус
        cursor.execute(
            "SELECT * FROM bonuses WHERE user_id = ? AND description = 'Registration bonus'",
            (user_id,)
        )
        if cursor.fetchone():
            return jsonify({"error": "Registration bonus already claimed"}), 400
        
        # Начисляем фиксированный бонус
        bonus_value = 100.0
        
        cursor.execute(
            "INSERT INTO bonuses (user_id, value, description) VALUES (?, ?, ?)",
            (user_id, bonus_value, "Registration bonus")
        )
        conn.commit()
        cursor.execute("UPDATE users  SET balance = balance+? WHERE user_id = ?;", (bonus_value,user_id))
        conn.commit()
        
        return jsonify({
            "success": True,
            "bonus": bonus_value,
            "message": "Registration bonus claimed successfully"
        }), 201

    except sqlite3.Error as e:
        print(e)
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()

# Ежедневный бонус
@app.route('/bonuses/<int:user_id>/daily', methods=['POST'])
def claim_daily_bonus(user_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Проверяем последнее получение бонуса
        cursor.execute(
            "SELECT day, getting_date FROM bonuses WHERE user_id = ? AND description = 'Daily bonus' ORDER BY getting_date DESC LIMIT 1",
            (user_id,)
        )
        day = 1
        last_claim = None
        result = cursor.fetchone()
        if result is not None:
            day, last_claim = result
            day += 1

        if last_claim:
            last_date = datetime.strptime(last_claim, "%Y-%m-%d %H:%M:%S")
            days_difference = (datetime.now()- last_date).days
            if days_difference < 1:
                return jsonify({"error": "Daily bonus already claimed today"}), 400
            elif days_difference >=2:
                day = 1
        
        # Начисляем фиксированный бонус
        if day > 5:
            bonus_value = day*5
        else:
            bonus_value = day*10
        
        cursor.execute(
            "INSERT INTO bonuses (user_id, value, description, day) VALUES (?, ?, ?, ?);",
            (user_id, bonus_value, "Daily bonus", day)
        )
        conn.commit()
        cursor.execute("UPDATE users  SET balance = balance+? WHERE user_id = ?;", (bonus_value,user_id))
        conn.commit()
        
        return jsonify({
            "success": True,
            "bonus": bonus_value,
            "message": "Daily bonus claimed successfully"
        }), 201

    except sqlite3.Error as e:
        print(e)
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    finally:
        conn.close()

@app.route('/api/participants/<int:user_id>', methods=['GET'])
def get_participants(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Выбираем всех участников, отсортированных по views (убывание)
    cursor.execute('''
        SELECT id, user_id, username, views, received
        FROM participants
        ORDER BY views DESC
    ''', (user_id,))

    participants = cursor.fetchall()

    # Преобразуем результат в список словарей
    participants_list = [dict(row) for row in participants]

    conn.close()
    return jsonify(participants_list)

app.run(debug=True)
