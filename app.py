import os
import time
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Load variabel environment dari file .env
load_dotenv()

app = Flask(__name__)
app.secret_key = 'kunci_rahasia_opung_sangat_aman'  # Dibutuhkan untuk sistem session login[cite: 3]

# Konfigurasi PostgreSQL dari file .env
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Konfigurasi Folder Upload Bukti Pembayaran
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

db = SQLAlchemy(app)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Model Tabel Database PostgreSQL ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    grade = db.Column(db.String(20), nullable=False)  # 'developer', 'admin', 'tamu'[cite: 3]

class Changelog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.String(20), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(80), nullable=False)
    date = db.Column(db.String(20), nullable=False)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20), nullable=False)
    type = db.Column(db.String(10), nullable=False)  # 'in' atau 'out'
    category = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200), nullable=True)
    proof_file = db.Column(db.String(200), nullable=True)  # Menyimpan nama file bukti pembayaran
    author = db.Column(db.String(80), nullable=False)

class LinkVault(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    author = db.Column(db.String(80), nullable=False)

class Savings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0.0)
    deadline = db.Column(db.String(20), nullable=True)
    author = db.Column(db.String(80), nullable=False)

# --- Routing Aplikasi ---
@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    changelogs = Changelog.query.order_by(Changelog.id.desc()).all()
    transactions = Transaction.query.all()
    
    total_in = sum(t.amount for t in transactions if t.type == 'in')
    total_out = sum(t.amount for t in transactions if t.type == 'out')
    balance = total_in - total_out

    # Auto-generate versi berikutnya
    next_version = "v1.0.1"
    if changelogs:
        latest_version = changelogs[0].version
        try:
            parts = latest_version.lstrip('v').split('.')
            if len(parts) == 3:
                parts[2] = str(int(parts[2]) + 1)
                next_version = f"v{'.'.join(parts)}"
        except:
            next_version = "v1.1.4"
    
    return render_template('index.html', changelogs=changelogs, total_in=total_in, total_out=total_out, balance=balance, next_version=next_version)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['username'] = user.username
            session['grade'] = user.grade
            flash('Login berhasil!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Username atau password salah!', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/manajemen-akun')
def manajemen_akun():
    # Hanya developer (Opung) yang bisa akses halaman ini[cite: 3]
    if session.get('grade') != 'developer':
        return "Akses ditolak! Halaman ini khusus Developer.", 403
        
    users = User.query.all()
    return render_template('manajemen_akun.html', users=users)

@app.route('/tambah-user', methods=['POST'])
def tambah_user():
    if session.get('grade') != 'developer':
        return "Akses ditolak!", 403
        
    username = request.form['username']
    password = request.form['password']
    grade = request.form['grade']
    
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        flash('Username sudah terdaftar!', 'danger')
        return redirect(url_for('manajemen_akun'))
        
    new_user = User(username=username, password=password, grade=grade)
    db.session.add(new_user)
    db.session.commit()
    
    flash('Akun baru berhasil ditambahkan ke database!', 'success')
    return redirect(url_for('manajemen_akun'))

@app.route('/hapus-user/<int:id>', methods=['POST'])
def hapus_user(id):
    if session.get('grade') != 'developer':
        return "Akses ditolak!", 403
        
    user_to_delete = User.query.get_or_404(id)
    if user_to_delete.username == session.get('username'):
        flash('Tidak dapat menghapus akun yang sedang digunakan!', 'danger')
        return redirect(url_for('manajemen_akun'))
        
    db.session.delete(user_to_delete)
    db.session.commit()
    
    flash('Akun berhasil dihapus dari database!', 'success')
    return redirect(url_for('manajemen_akun'))

@app.route('/edit-user/<int:id>', methods=['POST'])
def edit_user(id):
    if session.get('grade') != 'developer':
        return "Akses ditolak!", 403
        
    user = User.query.get_or_404(id)
    user.username = request.form['username']
    
    new_password = request.form['password']
    if new_password:
        user.password = new_password
        
    user.grade = request.form['grade']
    db.session.commit()
    
    flash('Data akun berhasil diperbarui!', 'success')
    return redirect(url_for('manajemen_akun'))

@app.route('/tambah-changelog', methods=['POST'])
def tambah_changelog():
    # Validasi hak akses: hanya developer yang bisa merilis update[cite: 3]
    if session.get('grade') != 'developer':
        return "Akses ditolak!", 403
        
    version = request.form['version']
    title = request.form['title']
    description = request.form['description']
    date = request.form['date']
    author = session.get('username', 'Opung')
    
    new_log = Changelog(version=version, title=title, description=description, author=author, date=date)
    db.session.add(new_log)
    db.session.commit()
    
    return redirect(url_for('index'))

@app.route('/keuangan')
def keuangan():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    transactions = Transaction.query.order_by(Transaction.id.desc()).all()
    
    # Hitung total pemasukan, pengeluaran, dan saldo akhir
    total_in = sum(t.amount for t in transactions if t.type == 'in')
    total_out = sum(t.amount for t in transactions if t.type == 'out')
    balance = total_in - total_out
    
    return render_template('keuangan.html', transactions=transactions, total_in=total_in, total_out=total_out, balance=balance)

@app.route('/tambah-transaksi', methods=['POST'])
def tambah_transaksi():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    date = request.form['date']
    trans_type = request.form['type']
    category = request.form['category']
    amount = float(request.form['amount'])
    description = request.form.get('description', '')
    author = session.get('username')
    
    # Menangani Upload File Bukti Pembayaran
    proof_filename = None
    if 'proof_file' in request.files:
        file = request.files['proof_file']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            unique_filename = f"{int(time.time())}_{filename}"
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            file.save(os.path.join(UPLOAD_FOLDER, unique_filename))
            proof_filename = unique_filename

    new_trans = Transaction(
        date=date, type=trans_type, category=category, 
        amount=amount, description=description, 
        proof_file=proof_filename, author=author
    )
    db.session.add(new_trans)
    db.session.commit()
    
    flash('Catatan keuangan dan bukti pembayaran berhasil ditambahkan!', 'success')
    return redirect(url_for('keuangan'))

@app.route('/hapus-transaksi/<int:id>', methods=['POST'])
def hapus_transaksi(id):
    if 'username' not in session:
        return redirect(url_for('login'))
        
    trans = Transaction.query.get_or_404(id)
    
    # Hapus file fisik jika ada
    if trans.proof_file:
        file_path = os.path.join(UPLOAD_FOLDER, trans.proof_file)
        if os.path.exists(file_path):
            os.remove(file_path)
            
    db.session.delete(trans)
    db.session.commit()
    
    flash('Catatan keuangan berhasil dihapus!', 'success')
    return redirect(url_for('keuangan'))

@app.route('/brangkas-link')
def brangkas_link():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    links = LinkVault.query.order_by(LinkVault.id.desc()).all()
    return render_template('brangkas_link.html', links=links)

@app.route('/tambah-link', methods=['POST'])
def tambah_link():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    title = request.form['title']
    url = request.form['url']
    category = request.form['category']
    author = session.get('username')
    
    new_link = LinkVault(title=title, url=url, category=category, author=author)
    db.session.add(new_link)
    db.session.commit()
    
    flash('Link penting berhasil disimpan ke Brangkas!', 'success')
    return redirect(url_for('brangkas_link'))

@app.route('/hapus-link/<int:id>', methods=['POST'])
def hapus_link(id):
    if 'username' not in session:
        return redirect(url_for('login'))
        
    link = LinkVault.query.get_or_404(id)
    db.session.delete(link)
    db.session.commit()
    
    flash('Link berhasil dihapus dari Brangkas!', 'success')
    return redirect(url_for('brangkas_link'))

@app.route('/tabungan')
def tabungan():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    savings_list = Savings.query.order_by(Savings.id.desc()).all()
    total_savings = sum(s.current_amount for s in savings_list)
    
    return render_template('tabungan.html', savings_list=savings_list, total_savings=total_savings)

@app.route('/tambah-tabungan', methods=['POST'])
def tambah_tabungan():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    title = request.form['title']
    target_amount = float(request.form['target_amount'])
    current_amount = float(request.form.get('current_amount', 0))
    deadline = request.form.get('deadline', '')
    author = session.get('username')
    
    new_saving = Savings(title=title, target_amount=target_amount, current_amount=current_amount, deadline=deadline, author=author)
    db.session.add(new_saving)
    db.session.commit()
    
    flash('Target tabungan berhasil ditambahkan!', 'success')
    return redirect(url_for('tabungan'))

@app.route('/update-tabungan/<int:id>', methods=['POST'])
def update_tabungan(id):
    if 'username' not in session:
        return redirect(url_for('login'))
        
    saving = Savings.query.get_or_404(id)
    add_amount = float(request.form.get('add_amount', 0))
    saving.current_amount += add_amount
    db.session.commit()
    
    flash('Tabungan berhasil diperbarui!', 'success')
    return redirect(url_for('tabungan'))

@app.route('/hapus-tabungan/<int:id>', methods=['POST'])
def hapus_tabungan(id):
    if 'username' not in session:
        return redirect(url_for('login'))
        
    saving = Savings.query.get_or_404(id)
    db.session.delete(saving)
    db.session.commit()
    
    flash('Target tabungan dihapus!', 'success')
    return redirect(url_for('tabungan'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Membuat tabel otomatis jika belum ada di database Aiven[cite: 3]
        
        # Seeding akun default (Developer Opung) jika database masih kosong[cite: 3]
        if not User.query.filter_by(username='Opung').first():
            default_dev = User(username='Opung', password='123', grade='developer')
            db.session.add(default_dev)
            db.session.commit()
            
    app.run(debug=True)