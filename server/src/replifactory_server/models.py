from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class ExperimentModel(db.Model):
    __tablename__ = 'experiments'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='created')
    parameters = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now)
    measurements = db.relationship('MeasurementData', backref='experiment', lazy=True)

class MeasurementData(db.Model):
    __tablename__ = 'measurements'
    id = db.Column(db.Integer, primary_key=True)
    experiment_id = db.Column(db.Integer, db.ForeignKey('experiments.id'), nullable=False)
    vial = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    od = db.Column(db.Float)
    temperature = db.Column(db.Float)
    drug_concentration = db.Column(db.Float)
    growth_rate = db.Column(db.Float) 