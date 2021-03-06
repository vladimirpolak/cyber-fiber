from flask import Flask, render_template, url_for, request, redirect, flash
from forms import RegisterForm, LoginForm, CreatePostForm
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_bootstrap import Bootstrap
from names import generate_name
from datetime import datetime
import requests
import os

app = Flask(__name__)
Bootstrap(app)


# SET SECRET KEY
if os.environ.get("SECRET_KEY"):
    app.secret_key = os.environ.get("SECRET_KEY")
else:
    app.secret_key = "12345"

# CONNECT DB
if os.environ.get("DATABASE_URL"):
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL').replace("://", "ql://", 1)
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///database.db"

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# LOGIN MANAGER
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


# FORM ERRORS
def flash_errors(form):
    """Flashes form errors"""
    for field, errors in form.errors.items():
        for error in errors:
            flash(u"Error in the %s field - %s" % (
                getattr(form, field).label.text,
                error
            ), 'error')


# CONFIGURE TABLES
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(250))
    email = db.Column(db.String(250), unique=True, nullable=False)
    age = db.Column(db.Integer, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    posts = relationship("Posts", back_populates="author")
    comments = relationship("Comments", back_populates="author")


class Posts(db.Model):
    __tablename__ = "posts"
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(250))
    title = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")
    comments = relationship("Comments", back_populates="post")


class Comments(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(250))
    comment = db.Column(db.Text, nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="comments")
    post_id = db.Column(db.Integer, db.ForeignKey("posts.id"))
    post = relationship("Posts", back_populates="comments")


db.create_all()


@app.route('/')
def index():
    response = requests.get("https://api.quotable.io/random?tags=wisdom")
    quote = response.json()

    return render_template("index.html", quote=quote)


@app.route("/feed-page")
@login_required
def feed_page():
    posts = Posts.query.all()
    return render_template("feed.html", posts=posts)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit() and request.method == "POST":

        # Get form input
        email = form.email.data

        user = User.query.filter_by(email=email).first()

        # Check user input
        if not user or not check_password_hash(user.password, form.password.data):
            flash('Please check your login details and try again.')
            return redirect(url_for('login'))

        user.username = generate_name()
        db.session.commit()

        login_user(user, remember=False)
        return redirect(url_for('feed_page'))

    # Flash form errors if there are any
    elif form.errors:
        flash_errors(form)

    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit() and request.method == "POST":

        # Get form input
        email = form.email.data
        age = form.age.data
        pass_hash = generate_password_hash(form.password.data, method="pbkdf2:sha256", salt_length=8)

        # Check if age is number
        if not age.isdigit():
            flash("Age must be number! :D")
            return render_template('register.html', form=form)

        # Check if email is unique
        user = User.query.filter_by(email=email).first()
        if user:  # if a user is found, we want to redirect back to signup page so user can try again
            flash("You've already signed up with that e-mail, log in instead!")
            return redirect(url_for('login'))

        # Check if passwords match
        if not check_password_hash(pass_hash, form.password_confirm.data):
            print("pass's do not match")
            flash("Passwords do not match!")
            return render_template('register.html', form=form)
        # form.errors.items()

        # Create new user database entry
        new_user = User(
            username=generate_name(),
            email=email,
            age=age,
            password=pass_hash
        )

        db.session.add(new_user)
        db.session.commit()

        login_user(new_user, remember=False)
        return redirect(url_for('feed_page'))

    # Flash form errors if there are any
    elif form.errors:
        flash_errors(form)

    return render_template('register.html', form=form)


@app.route('/new-post', methods=["GET", "POST"])
@login_required
def new_post():
    form = CreatePostForm()
    if form.validate_on_submit() and request.method == "POST":
        title = form.title.data
        body = form.body.data
        today = datetime.now()
        date = today.strftime("%d/%m/%Y")

        db_new_post = Posts(
            date=date,
            title=title,
            body=body,
            author=current_user,
        )

        db.session.add(db_new_post)
        db.session.commit()

        return redirect(url_for('feed_page'))

    # Flash form errors if there are any
    elif form.errors:
        flash_errors(form)

    return render_template('new_post.html', form=form)


@app.route('/delete-post/<int:post_id>')
def delete_post(post_id):
    # Get post to be deleted
    post = Posts.query.get(post_id)

    # Delete post
    db.session.delete(post)
    db.session.commit()

    return redirect(url_for('feed_page'))


@login_required
@app.route('/profile')
def profile():
    user_posts = Posts.query.filter_by(author=current_user)
    return render_template('profile.html', user_posts=user_posts)


@login_required
@app.route('/change-name')
def change_name():
    current_user.username = generate_name()

    db.session.commit()
    return redirect(url_for('profile'))


if __name__ == '__main__':
    app.run()
