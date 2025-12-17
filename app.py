from flask import Flask, render_template, request, redirect, url_for, flash
import os
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import random
from datetime import datetime

app = Flask(__name__)
# Use environment variables for secrets and database in production
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///instance/database.db')
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)


class Record(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total_co2 = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


NATIONAL_AVERAGE = 70
ECO_TIPS = [
    "Switch to LED bulbs to save energy.",
    "Walk or bike short distances.",
    "Recycle household waste.",
    "Try one meat-free day per week.",
    "Turn off devices when not in use."
]


def get_ai_tips(travel, electricity, food, waste):
    tips = []
    if travel > 50:
        tips.append("Your travel emissions are high — use public transport or carpool.")
    if electricity > 30:
        tips.append("Reduce electricity use — switch to energy-efficient appliances.")
    if food > 10:
        tips.append("Cut down on meat meals — try plant-based options.")
    if waste > 5:
        tips.append("Recycle and compost your waste regularly.")
    return tips


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already exists.')
            return redirect(url_for('register'))
        pw_hash = generate_password_hash(password)
        new_user = User(username=username, password=pw_hash)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('calculator'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('calculator'))
        flash('Invalid credentials.')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/calculator')
@login_required
def calculator():
    return render_template('calculator.html')


GLOBAL_STATS = {
    "Global Average": 4.5,
    "USA": 14.4,
    "India": 1.9,
    "China": 7.6,
    "European Union": 6.5,
    "Africa": 0.9
}


@app.route('/calculate', methods=['GET', 'POST'])
@login_required
def calculate():
    if request.method == 'GET':
        return redirect(url_for('calculator'))

    try:
        period_map = {'daily': 1, 'weekly': 7, 'monthly': 30}
        period = request.form.get('period', 'weekly')
        multiplier = period_map.get(period, 7)

        travel = float(request.form['distance'])
        electricity = float(request.form['electricity'])
        food = float(request.form['meals'])
        waste = float(request.form['waste'])

        travel_co2 = travel * 0.271 * multiplier
        electricity_co2 = electricity * 0.475 * multiplier
        food_co2 = food * 0.5
        waste_co2 = waste * 0.1

        if period == 'daily':
            food_co2 = food * 0.5 / 7
            waste_co2 = waste * 0.1 / 7
        elif period == 'monthly':
            food_co2 = food * 0.5 * 4.3
            waste_co2 = waste * 0.1 * 4.3

        total_co2 = round(travel_co2 + electricity_co2 + food_co2 + waste_co2, 2)

        if total_co2 > 0:
            pie_data = {
                'travel': round((travel_co2 / total_co2) * 100, 2),
                'electricity': round((electricity_co2 / total_co2) * 100, 2),
                'food': round((food_co2 / total_co2) * 100, 2),
                'waste': round((waste_co2 / total_co2) * 100, 2),
            }
        else:
            pie_data = {'travel': 0, 'electricity': 0, 'food': 0, 'waste': 0}

        user_annual_tons = (total_co2 * (365 / multiplier)) / 1000

        ai_global_insights = []
        if user_annual_tons > 14:
            ai_global_insights.append("Your footprint is higher than the average American — focus on reducing energy use and travel.")
        elif user_annual_tons > 4.5:
            ai_global_insights.append("You’re above the global average — small changes like LED lighting and fewer car trips can help.")
        elif user_annual_tons > 2:
            ai_global_insights.append("You’re near sustainable levels — keep minimizing waste and electricity use.")
        else:
            ai_global_insights.append("You're performing better than most people worldwide. Great job being eco-conscious!")

        if total_co2 < 20:
            badge = ("🌱 Eco Hero", "success")
        elif total_co2 < 50:
            badge = ("⚖️ Average Citizen", "warning")
        else:
            badge = ("🔥 Heavy Emitter", "danger")

        new_record = Record(user_id=current_user.id, total_co2=total_co2)
        db.session.add(new_record)
        db.session.commit()

        results = {
            'total_co2': total_co2,
            'pie_data': pie_data,
            'national_average': 70,
            'comparison': round(((total_co2 - 70) / 70) * 100, 1) if multiplier == 7 else None,
            'eco_tips': random.sample(ECO_TIPS, 3),
            'ai_tips': get_ai_tips(travel, electricity, food, waste),
            'badge': badge,
            'global_stats': GLOBAL_STATS,
            'user_annual_tons': round(user_annual_tons, 2),
            'ai_global_insights': ai_global_insights
        }

        return render_template('result.html', results=results)
    except (KeyError, ValueError):
        flash('Invalid input. Please enter valid numbers.')
        return redirect(url_for('calculator'))


@app.route('/leaderboard')
@login_required
def leaderboard():
    subquery = db.session.query(Record.user_id, db.func.min(Record.total_co2).label('min_co2')).group_by(Record.user_id).subquery()
    users = db.session.query(User, subquery.c.min_co2).join(subquery, User.id == subquery.c.user_id).order_by(subquery.c.min_co2).limit(5).all()
    return render_template('leaderboard.html', users=users)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)