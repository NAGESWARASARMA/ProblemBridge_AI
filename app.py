from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from pathlib import Path
from datetime import datetime
import sqlite3, uuid, os

app = Flask(__name__)
app.secret_key = os.environ.get("PROBLEMBRIDGE_SECRET", "replace-this-secret-before-public-deployment")
ROOT = Path(__file__).resolve().parent
DB = ROOT / "problembridge.db"
UPLOADS = ROOT / "uploads"
UPLOADS.mkdir(exist_ok=True)
ALLOWED = {"png","jpg","jpeg","gif","pdf","txt","md","zip","py","js","html","css","json","csv","docx","xlsx","pptx"}

CATEGORIES = ["Agriculture","Business","Education","Health","Technology","Transportation","Environment","Community","Other"]
def stamp(): return datetime.now().strftime("%Y-%m-%d %H:%M")
def connect():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute("PRAGMA foreign_keys=ON"); return c

def init_db():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS problems(id INTEGER PRIMARY KEY, poster_id INTEGER NOT NULL REFERENCES users(id), title TEXT NOT NULL, description TEXT NOT NULL, requirements TEXT NOT NULL, category TEXT NOT NULL, model TEXT NOT NULL, budget REAL, deadline TEXT, status TEXT NOT NULL DEFAULT 'open', views INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS solutions(id INTEGER PRIMARY KEY, problem_id INTEGER NOT NULL REFERENCES problems(id), solver_id INTEGER NOT NULL REFERENCES users(id), description TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'submitted', created TEXT NOT NULL, UNIQUE(problem_id,solver_id));
        CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY, solution_id INTEGER NOT NULL REFERENCES solutions(id), original TEXT NOT NULL, stored TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, problem_id INTEGER NOT NULL REFERENCES problems(id), sender_id INTEGER NOT NULL REFERENCES users(id), receiver_id INTEGER NOT NULL REFERENCES users(id), body TEXT NOT NULL, created TEXT NOT NULL);
        """)
        if c.execute("SELECT COUNT(*) FROM problems").fetchone()[0] == 0:
            c.execute("INSERT INTO users(username,email,password,created) VALUES(?,?,?,?)",("demo_poster","poster@example.com",generate_password_hash("demo-password-123"),stamp()))
            pid=c.execute("SELECT id FROM users WHERE username='demo_poster'").fetchone()[0]
            c.execute("INSERT INTO problems(poster_id,title,description,requirements,category,model,budget,status,views,created) VALUES(?,?,?,?,?,?,?,?,?,?)",
              (pid,"DEMO: College bus arrival updates","SAMPLE PROJECT — A college wants a simple way to share bus arrival and departure updates.","Show bus number, route, event time and recent scan history. This is demo content, not a real request.","Transportation","free",None,"open",48,stamp()))
            c.execute("INSERT INTO problems(poster_id,title,description,requirements,category,model,budget,status,views,created) VALUES(?,?,?,?,?,?,?,?,?,?)",
              (pid,"DEMO: Small shop order tracker","SAMPLE PROJECT — A shop wants to track orders and their status.","Create an order list, status updates and a summary. This is demo content, not a real request.","Business","paid",3500,"open",35,stamp()))
            c.execute("INSERT INTO problems(poster_id,title,description,requirements,category,model,budget,status,views,created) VALUES(?,?,?,?,?,?,?,?,?,?)",
              (pid,"DEMO: Crop watering reminder","SAMPLE COMPLETED PROJECT — Prototype a reminder calendar for crop watering checks.","A calendar, reminders and simple notes. This sample is not a verified real-world deployment.","Agriculture","free",None,"solved",92,stamp()))
            c.execute("INSERT INTO users(username,email,password,created) VALUES(?,?,?,?)",("demo_solver","solver@example.com",generate_password_hash("demo-password-123"),stamp()))
            sid=c.execute("SELECT id FROM users WHERE username='demo_solver'").fetchone()[0]
            p=c.execute("SELECT id FROM problems WHERE title LIKE 'DEMO: Crop watering reminder'").fetchone()[0]
            c.execute("INSERT INTO solutions(problem_id,solver_id,description,status,created) VALUES(?,?,?,?,?)",(p,sid,"SAMPLE solution summary; replace this with a real submitted project.","accepted",stamp()))

def user():
    if not session.get("uid"): return None
    with connect() as c: return c.execute("SELECT id,username,email FROM users WHERE id=?",(session["uid"],)).fetchone()

@app.context_processor
def shared(): return {"current_user":user(),"categories":CATEGORIES}

@app.route("/")
def home():
    with connect() as c:
        solved=c.execute("""SELECT p.*,u.username poster_name,su.username solver_name FROM problems p JOIN users u ON u.id=p.poster_id LEFT JOIN solutions s ON s.problem_id=p.id AND s.status='accepted' LEFT JOIN users su ON su.id=s.solver_id WHERE p.status='solved' ORDER BY p.views DESC LIMIT 6""").fetchall()
    return render_template("home.html",solved=solved)

@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="POST":
        name=request.form.get("username","").strip(); email=request.form.get("email","").strip().lower(); pw=request.form.get("password","")
        if len(name)<3 or "@" not in email or len(pw)<8: flash("Enter a username (3+ characters), valid email and password (8+ characters).","error")
        else:
            try:
                with connect() as c: c.execute("INSERT INTO users(username,email,password,created) VALUES(?,?,?,?)",(name,email,generate_password_hash(pw),stamp()))
                flash("Account created. You can now log in.","success"); return redirect(url_for("login"))
            except sqlite3.IntegrityError: flash("Username or email already exists.","error")
    return render_template("auth.html",mode="register")

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        ident=request.form.get("identifier","").strip()
        with connect() as c: row=c.execute("SELECT * FROM users WHERE username=? OR email=?",(ident,ident.lower())).fetchone()
        if row and check_password_hash(row["password"],request.form.get("password","")):
            session.clear(); session["uid"]=row["id"]; return redirect(url_for("home"))
        flash("Incorrect login details.","error")
    return render_template("auth.html",mode="login")

@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("home"))

@app.route("/post",methods=["GET","POST"])
def post():
    if not user(): flash("Please log in to publish a problem.","error"); return redirect(url_for("login"))
    if request.method=="POST":
        title=request.form.get("title","").strip(); desc=request.form.get("description","").strip(); reqs=request.form.get("requirements","").strip()
        category=request.form.get("category","Other"); model=request.form.get("model","free"); deadline=request.form.get("deadline","").strip() or None
        budget=None
        if model=="paid":
            try: budget=float(request.form.get("budget",""))
            except ValueError: budget=0
        if not title or not desc or not reqs: flash("Complete the title, problem statement and requirements.","error")
        elif model not in ("free","paid") or category not in CATEGORIES: flash("Choose a valid project type and category.","error")
        elif model=="paid" and (not budget or budget<=0): flash("Enter a paid-project budget greater than zero.","error")
        else:
            with connect() as c:
                c.execute("INSERT INTO problems(poster_id,title,description,requirements,category,model,budget,deadline,created) VALUES(?,?,?,?,?,?,?,?,?)",
                    (user()["id"],title,desc,reqs,category,model,budget,deadline,stamp()))
                pid=c.execute("SELECT last_insert_rowid()").fetchone()[0]
            flash("Problem published successfully.","success"); return redirect(url_for("detail",pid=pid))
    return render_template("post.html")

@app.route("/solve")
def solve():
    model=request.args.get("model","free")
    if model not in ("free","paid"): model="free"
    category=request.args.get("category",""); q=request.args.get("q","").strip(); sort=request.args.get("sort","popular")
    sql="SELECT p.*,u.username poster_name FROM problems p JOIN users u ON u.id=p.poster_id WHERE p.status='open' AND p.model=?"; args=[model]
    if category in CATEGORIES: sql+=" AND p.category=?"; args.append(category)
    if q: sql+=" AND (p.title LIKE ? OR p.description LIKE ? OR p.requirements LIKE ?)"; args.extend([f"%{q}%"]*3)
    sql+=" ORDER BY "+("p.views DESC" if sort=="popular" else "p.created DESC")+" LIMIT 100"
    with connect() as c: rows=c.execute(sql,args).fetchall()
    return render_template("solve.html",problems=rows,model=model,q=q,category=category,sort=sort)

@app.route("/problem/<int:pid>")
def detail(pid):
    with connect() as c:
        c.execute("UPDATE problems SET views=views+1 WHERE id=?",(pid,))
        p=c.execute("SELECT p.*,u.username poster_name FROM problems p JOIN users u ON u.id=p.poster_id WHERE p.id=?",(pid,)).fetchone()
        if not p: abort(404)
        solutions=c.execute("SELECT s.*,u.username solver_name FROM solutions s JOIN users u ON u.id=s.solver_id WHERE s.problem_id=? ORDER BY s.created DESC",(pid,)).fetchall()
    return render_template("problem.html",p=p,solutions=solutions)

@app.route("/problem/<int:pid>/solution",methods=["POST"])
def submit(pid):
    me=user()
    if not me: flash("Log in to submit a solution.","error"); return redirect(url_for("login"))
    desc=request.form.get("description","").strip()
    if not desc: flash("Describe your solution and files.","error"); return redirect(url_for("detail",pid=pid))
    with connect() as c:
        p=c.execute("SELECT * FROM problems WHERE id=?",(pid,)).fetchone()
        if not p: abort(404)
        if p["poster_id"]==me["id"]: flash("You cannot solve your own posted problem.","error"); return redirect(url_for("detail",pid=pid))
        try:
            c.execute("INSERT INTO solutions(problem_id,solver_id,description,created) VALUES(?,?,?,?)",(pid,me["id"],desc,stamp()))
            sid=c.execute("SELECT last_insert_rowid()").fetchone()[0]
        except sqlite3.IntegrityError:
            flash("You have already submitted a solution for this problem.","error"); return redirect(url_for("detail",pid=pid))
        folder=UPLOADS/str(sid); folder.mkdir(parents=True,exist_ok=True)
        for f in request.files.getlist("files"):
            if f and f.filename and "." in f.filename and f.filename.rsplit(".",1)[1].lower() in ALLOWED:
                original=secure_filename(f.filename); stored=uuid.uuid4().hex+"_"+original; f.save(folder/stored)
                c.execute("INSERT INTO files(solution_id,original,stored) VALUES(?,?,?)",(sid,original,stored))
    flash("Solution submitted. The problem deployer can review it and contact you in project chat.","success")
    return redirect(url_for("detail",pid=pid))

@app.route("/solution/<int:sid>/accept",methods=["POST"])
def accept(sid):
    me=user()
    if not me: return redirect(url_for("login"))
    with connect() as c:
        s=c.execute("SELECT s.*,p.poster_id,p.id pid FROM solutions s JOIN problems p ON p.id=s.problem_id WHERE s.id=?",(sid,)).fetchone()
        if not s: abort(404)
        if s["poster_id"]!=me["id"]: abort(403)
        c.execute("UPDATE solutions SET status='accepted' WHERE problem_id=?",(s["pid"],))
        c.execute("UPDATE problems SET status='solved' WHERE id=?",(s["pid"],))
    flash("Solution accepted. The project now appears in Solved Problems.","success")
    return redirect(url_for("detail",pid=s["pid"]))

@app.route("/solved")
def solved():
    q=request.args.get("q","").strip()
    sql="""SELECT p.*,u.username poster_name,su.username solver_name FROM problems p JOIN users u ON u.id=p.poster_id
       LEFT JOIN solutions s ON s.problem_id=p.id AND s.status='accepted' LEFT JOIN users su ON su.id=s.solver_id WHERE p.status='solved'"""
    args=[]
    if q: sql+=" AND (p.title LIKE ? OR p.description LIKE ?)"; args=[f"%{q}%"]*2
    sql+=" ORDER BY p.views DESC,p.created DESC"
    with connect() as c: rows=c.execute(sql,args).fetchall()
    return render_template("solved.html",projects=rows,q=q)

@app.route("/dashboard")
def dashboard():
    me=user()
    if not me: return redirect(url_for("login"))
    with connect() as c:
        posted=c.execute("SELECT * FROM problems WHERE poster_id=? ORDER BY created DESC",(me["id"],)).fetchall()
        solutions=c.execute("SELECT s.*,p.title,p.model,p.status problem_status FROM solutions s JOIN problems p ON p.id=s.problem_id WHERE s.solver_id=? ORDER BY s.created DESC",(me["id"],)).fetchall()
    return render_template("dashboard.html",posted=posted,submissions=solutions)

@app.route("/chat/<int:pid>",methods=["GET","POST"])
def chat(pid):
    me=user()
    if not me: return redirect(url_for("login"))
    with connect() as c:
        p=c.execute("SELECT * FROM problems WHERE id=?",(pid,)).fetchone()
        if not p: abort(404)
        has=c.execute("SELECT 1 FROM solutions WHERE problem_id=? AND solver_id=?",(pid,me["id"])).fetchone()
        if me["id"]!=p["poster_id"] and not has: abort(403)
        people=c.execute("SELECT id,username FROM users WHERE id=? OR id IN (SELECT solver_id FROM solutions WHERE problem_id=?) ORDER BY username",(p["poster_id"],pid)).fetchall()
        peer=request.args.get("with_user","")
        if not peer.isdigit():
            options=[x["id"] for x in people if x["id"]!=me["id"]]
            peer=str(options[0]) if options else str(me["id"])
        peer=int(peer)
        valid=any(x["id"]==peer for x in people)
        if not valid: abort(403)
        if request.method=="POST":
            body=request.form.get("body","").strip()
            if body:
                c.execute("INSERT INTO messages(problem_id,sender_id,receiver_id,body,created) VALUES(?,?,?,?,?)",(pid,me["id"],peer,body[:4000],stamp()))
                return redirect(url_for("chat",pid=pid,with_user=peer))
        msgs=c.execute("SELECT m.*,u.username sender_name FROM messages m JOIN users u ON u.id=m.sender_id WHERE m.problem_id=? AND ((sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?)) ORDER BY m.created",(pid,me["id"],peer,peer,me["id"])).fetchall()
    return render_template("chat.html",p=p,people=people,peer=peer,messages=msgs)

@app.route("/file/<int:sid>/<path:stored>")
def file_download(sid,stored):
    me=user()
    if not me: abort(403)
    with connect() as c:
        row=c.execute("SELECT f.*,p.poster_id,s.solver_id FROM files f JOIN solutions s ON s.id=f.solution_id JOIN problems p ON p.id=s.problem_id WHERE s.id=? AND f.stored=?",(sid,stored)).fetchone()
        if not row: abort(404)
        if me["id"] not in (row["poster_id"],row["solver_id"]): abort(403)
    return send_from_directory(UPLOADS/str(sid),stored,as_attachment=True,download_name=row["original"])

@app.errorhandler(403)
def forbidden(e): return render_template("message.html",title="Access restricted",message="You do not have permission to access this page."),403
@app.errorhandler(404)
def not_found(e): return render_template("message.html",title="Not found",message="This page does not exist."),404

init_db()
if __name__=="__main__":
    app.run(debug=True)
