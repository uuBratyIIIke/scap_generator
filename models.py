from enum import Enum
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class OperationEnum(str, Enum):
    EQUALS = "equals"
    NOT_EQUAL = "not equal"
    GREATER_THAN = "greater than"
    LESS_THAN = "less than"
    PATTERN_MATCH = "pattern match"

groups_to_profile = db.Table(
    'groups_to_profile',
    db.Column('id', db.Integer, primary_key=True),
    db.Column('profile_id', db.Integer, db.ForeignKey('profile.id'), nullable=False),
    db.Column('group_id', db.Integer, db.ForeignKey('groups.id'), nullable=False)
)

class Group(db.Model):
    __tablename__ = 'groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)

class Parameter(db.Model):
    __tablename__ = 'parameter'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'))
    comment = db.Column(db.String(255), nullable=True)
    title = db.Column(db.String(255), nullable=True)
    operation = db.Column(db.String(255), nullable=True)

    __table_args__ = (
        db.Index('ix_parameters_name', name, mysql_length=255),
        {'mysql_engine': 'InnoDB'}
    )

    group = db.relationship('Group', backref='parameter')

    def __repr__(self):
        return f'<Parameter {self.name}>'

class Profile(db.Model):
    __tablename__ = 'profile'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    description = db.Column(db.String)
    is_selected = db.Column(db.Boolean)
    severity = db.Column(db.String(64))
    title = db.Column(db.String(255), nullable=True)
    content_href = db.Column(db.String(512))
    groups = db.relationship(
        'Group',
        secondary=groups_to_profile,
        backref=db.backref('profiles', lazy='dynamic')
    )
