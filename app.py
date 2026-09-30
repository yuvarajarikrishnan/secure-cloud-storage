from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import zipfile

app = Flask(__name__)

# Secret key
app.config["SECRET_KEY"] = "secure-cloud-storage-secret-key"
# 10 MB maximum per individual file
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

# 5 GB maximum storage per user
MAX_STORAGE_PER_USER = 5 * 1024 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "pdf",
    "txt",
    "docx",
    "xlsx"
}
def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def get_user_storage(user_id):
    user_folder = os.path.join(
        app.config["UPLOAD_FOLDER"],
        str(user_id)
    )

    if not os.path.exists(user_folder):
        return 0

    total_size = 0

    for filename in os.listdir(user_folder):
        file_path = os.path.join(user_folder, filename)

        if os.path.isfile(file_path):
            total_size += os.path.getsize(file_path)

    return total_size
# Database
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Login system
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Upload folder
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# User database model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# Home page
@app.route("/")
@login_required
def home():
    user_folder = os.path.join(
        UPLOAD_FOLDER,
        str(current_user.id)
    )

    os.makedirs(user_folder, exist_ok=True)

    files = os.listdir(user_folder)

    storage_used = get_user_storage(current_user.id)

    return render_template(
        "index.html",
        files=files,
        storage_used=storage_used,
        storage_limit=MAX_STORAGE_PER_USER
    )
    user_folder = os.path.join(
        UPLOAD_FOLDER,
        str(current_user.id)
    )

    os.makedirs(user_folder, exist_ok=True)

    files = os.listdir(user_folder)

    return render_template("index.html", files=files)


# Signup
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        existing_user = User.query.filter_by(username=username).first()

        if existing_user:
            return "Username already exists!"

        hashed_password = generate_password_hash(password)

        new_user = User(
            username=username,
            password=hashed_password
        )

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("signup.html")


# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("home"))

        return "Invalid username or password!"

    return render_template("login.html")


# Logout
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# Upload
@app.route("/upload", methods=["POST"])
@login_required
def upload_file():
    file = request.files.get("file")

    if file and file.filename:
        if not allowed_file(file.filename):
            flash(
                "File type not allowed! Please upload PNG, JPG, PDF, TXT, DOCX, or XLSX.",
                "error"
            )
            return redirect(url_for("home"))

        user_folder = os.path.join(
            app.config["UPLOAD_FOLDER"],
            str(current_user.id)
        )

        os.makedirs(user_folder, exist_ok=True)

        safe_filename = secure_filename(file.filename)

        # Get the actual file size
        file.seek(0, os.SEEK_END)
        new_file_size = file.tell()
        file.seek(0)

        # Get current storage used by this user
        current_storage = get_user_storage(current_user.id)

        # Check 5 GB storage limit
        if current_storage + new_file_size > MAX_STORAGE_PER_USER:
            flash(
                "Storage limit reached! You can store up to 5 GB.",
                "error"
            )
            return redirect(url_for("home"))

        # Save the file
        file.save(
            os.path.join(
                user_folder,
                safe_filename
            )
        )

        flash("File uploaded successfully!", "success")

    return redirect(url_for("home"))

# Download
@app.route("/download/<filename>")
@login_required
def download_file(filename):
    user_folder = os.path.join(
        app.config["UPLOAD_FOLDER"],
        str(current_user.id)
    )

    safe_filename = secure_filename(filename)

    return send_from_directory(
        user_folder,
        safe_filename,
        as_attachment=True
    )
# Delete
@app.route("/delete/<filename>")
@login_required
def delete_file(filename):
    user_folder = os.path.join(
        app.config["UPLOAD_FOLDER"],
        str(current_user.id)
    )

    safe_filename = secure_filename(filename)

    file_path = os.path.join(
        user_folder,
        safe_filename
    )

    if os.path.exists(file_path):
        os.remove(file_path)

    return redirect(url_for("home"))


@app.route("/download-all")
@login_required
def download_all():
    user_folder = os.path.join(
        app.config["UPLOAD_FOLDER"],
        str(current_user.id)
    )

    zip_path = os.path.join(
        user_folder,
        "my_files.zip"
    )

    with zipfile.ZipFile(zip_path, "w") as zipf:
        for filename in os.listdir(user_folder):
            file_path = os.path.join(
                user_folder,
                filename
            )

            if os.path.isfile(file_path) and filename != "my_files.zip":
                zipf.write(
                    file_path,
                    filename
                )

    return send_from_directory(
        user_folder,
        "my_files.zip",
        as_attachment=True
    )


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)

# Create database
with app.app_context():
    db.create_all()


# Start application
if __name__ == "__main__":
    app.run(debug=True)