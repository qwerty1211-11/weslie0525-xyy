from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///plan.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = '0525'
db = SQLAlchemy(app)
class User(db.Model):
    __tablename__ = 'weslie'
    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(50))
    description = db.Column(db.String(20))
with app.app_context():
    db.create_all()
@app.route('/')
def hello_word():
    return 'Hello, World!'
@app.route('/add plan', methods=['POST'])
def add_plan():
    data = request.get_json()
    time = data.get('time')
    title = data.get('title')
    description = data.get('description')
    plan = User(time=time, title=title, description=description)
    db.session.add(plan)
    db.session.commit()
    return jsonify({"msg": "添加成功"})
if __name__ == '__main__':
    app.run('0.0.0.0', 5000, debug=True)
