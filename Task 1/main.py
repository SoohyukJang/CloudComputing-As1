import os
import uuid
from datetime import datetime, timezone

from flask import Flask, request, session, redirect, url_for, render_template
from google.cloud import datastore, storage
from google.cloud.datastore.query import PropertyFilter

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCLOUD_PROJECT")
BUCKET_NAME = f"{PROJECT_ID}.appspot.com"

ds_client = datastore.Client()
storage_client = storage.Client()


def upload_image(file_storage, prefix):
    if not file_storage or file_storage.filename == "":
        return None
    bucket = storage_client.bucket(BUCKET_NAME)
    ext = os.path.splitext(file_storage.filename)[1]
    blob = bucket.blob(f"{prefix}/{uuid.uuid4().hex}{ext}")
    blob.upload_from_file(
        file_storage.stream,
        content_type=file_storage.content_type,
        predefined_acl="publicRead",
    )
    return blob.public_url


def find_user_by_property(name, value):
    query = ds_client.query(kind="user")
    query.add_filter(filter=PropertyFilter(name, "=", value))
    results = list(query.fetch(limit=1))
    return results[0] if results else None


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return find_user_by_property("id", user_id)


@app.route("/")
def root():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user_id = request.form["id"]
        password = request.form["password"]
        user = find_user_by_property("id", user_id)
        if not user or user["password"] != password:
            return render_template("login.html", error="ID or password is invalid")
        session["user_id"] = user["id"]
        return redirect(url_for("forum"))
    return render_template("login.html", error=None)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        user_id = request.form["id"]
        user_name = request.form["user_name"]
        password = request.form["password"]

        if find_user_by_property("id", user_id):
            return render_template("signup.html", error="The ID already exists")
        if find_user_by_property("user_name", user_name):
            return render_template("signup.html", error="The username already exists")

        image_url = upload_image(request.files.get("image"), "avatars")

        entity = datastore.Entity(ds_client.key("user"))
        entity.update({
            "id": user_id,
            "user_name": user_name,
            "password": password,
            "image_url": image_url,
        })
        ds_client.put(entity)
        return redirect(url_for("login"))
    return render_template("signup.html", error=None)


@app.route("/forum", methods=["GET", "POST"])
def forum():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        image_url = upload_image(request.files.get("image"), "posts")
        entity = datastore.Entity(ds_client.key("post"))
        entity.update({
            "subject": request.form["subject"],
            "message": request.form["message"],
            "image_url": image_url,
            "author_id": user["id"],
            "author_name": user["user_name"],
            "author_image_url": user["image_url"],
            "created_at": datetime.now(timezone.utc),
        })
        ds_client.put(entity)
        return redirect(url_for("forum"))

    query = ds_client.query(kind="post")
    query.order = ["-created_at"]
    posts = list(query.fetch(limit=10))
    return render_template("forum.html", user=user, posts=posts)


@app.route("/user/<user_id>")
def user_page(user_id):
    viewer = current_user()
    if not viewer:
        return redirect(url_for("login"))

    profile_user = find_user_by_property("id", user_id)
    if not profile_user:
        return redirect(url_for("forum"))

    query = ds_client.query(kind="post")
    query.add_filter(filter=PropertyFilter("author_id", "=", user_id))
    query.order = ["-created_at"]
    posts = list(query.fetch())

    is_owner = viewer["id"] == user_id
    return render_template(
        "user.html",
        viewer=viewer,
        profile_user=profile_user,
        posts=posts,
        is_owner=is_owner,
        error=None,
    )


@app.route("/user/<user_id>/change-password", methods=["POST"])
def change_password(user_id):
    viewer = current_user()
    if not viewer or viewer["id"] != user_id:
        return redirect(url_for("login"))

    old_password = request.form["old_password"]
    new_password = request.form["new_password"]

    if viewer["password"] != old_password:
        posts_query = ds_client.query(kind="post")
        posts_query.add_filter(filter=PropertyFilter("author_id", "=", user_id))
        posts_query.order = ["-created_at"]
        return render_template(
            "user.html",
            viewer=viewer,
            profile_user=viewer,
            posts=list(posts_query.fetch()),
            is_owner=True,
            error="The old password is incorrect",
        )

    viewer["password"] = new_password
    ds_client.put(viewer)
    session.clear()
    return redirect(url_for("login"))


@app.route("/user/<user_id>/post/<int:post_id>/edit", methods=["GET", "POST"])
def edit_post(user_id, post_id):
    viewer = current_user()
    if not viewer or viewer["id"] != user_id:
        return redirect(url_for("login"))

    key = ds_client.key("post", post_id)
    post = ds_client.get(key)
    if not post or post["author_id"] != user_id:
        return redirect(url_for("forum"))

    if request.method == "POST":
        post["subject"] = request.form["subject"]
        post["message"] = request.form["message"]
        new_image_url = upload_image(request.files.get("image"), "posts")
        if new_image_url:
            post["image_url"] = new_image_url
        post["created_at"] = datetime.now(timezone.utc)
        ds_client.put(post)
        return redirect(url_for("forum"))

    return render_template("edit_post.html", viewer=viewer, post=post)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8081, debug=True)
