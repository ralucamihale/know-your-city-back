from flask import Blueprint, request, jsonify
from .extensions import db
from .models import User, Grid, UnlockedCell
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
import math

main = Blueprint('main', __name__)
SECRET_KEY = "cheie_secreta_pentru_proiect_isi" # Schimbati in productie

# Task 2: Management utilizatori (Register/Login) [cite: 73]
@main.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    hashed_pw = generate_password_hash(data['password'])
    new_user = User(email=data['email'], password_hash=hashed_pw)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'User registered successfully'}), 201

@main.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data['email']).first()
    if not user or not check_password_hash(user.password_hash, data['password']):
        return jsonify({'message': 'Login failed'}), 401
    
    token = jwt.encode({'user_id': str(user.id), 'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)}, SECRET_KEY)
    return jsonify({'token': token})

@main.route('/api/explore', methods=['POST'])
def explore_cell():
    """
    Task 3 & 10: Primește GPS, calculează celula și o deblochează.
    """
    data = request.get_json()
    user_lat = data.get('lat')
    user_lng = data.get('lng')
    user_id = data.get('user_id') # În realitate luăm din token, simplificăm pentru MVP
    
    # 1. Găsim grid-ul activ al userului (sau primul grid creat)
    # Pentru MVP presupunem grid_id = 1 sau îl luăm din DB
    grid = Grid.query.first() 
    if not grid:
        return jsonify({'message': 'No grid defined'}), 404

    # 2. Luăm centrul grid-ului (presupunem format simplu sau facem parsing)
    # Nota: PostGIS returnează obiecte complexe, aici simplificăm logica matematică
    # Presupunem centrul fix pentru MVP (București - Piața Unirii)
    center_lat = 44.4268
    center_lng = 26.1025
    cell_size = 50 # metri (conform doc)

    # 3. Calculăm distanța față de centru în metri (Aproximare simplă)
    # 1 grad latitudine ~= 111.32 km
    delta_lat_m = (user_lat - center_lat) * 111320
    # 1 grad longitudine ~= 40075 km * cos(lat) / 360
    delta_lng_m = (user_lng - center_lng) * (40075000 * math.cos(math.radians(center_lat)) / 360)

    # 4. Determinăm indexul rândului și coloanei
    row_idx = math.floor(delta_lat_m / cell_size)
    col_idx = math.floor(delta_lng_m / cell_size)

    # 5. Verificăm limitele grid-ului (ex: 100x100)
    limit = grid.dimension // 2
    if abs(row_idx) > limit or abs(col_idx) > limit:
        return jsonify({'status': 'out_of_bounds'})

    # 6. Salvăm în baza de date dacă nu e deja deblocat
    existing = UnlockedCell.query.filter_by(grid_id=grid.id, row_index=row_idx, col_index=col_idx).first()
    
    if not existing:
        new_cell = UnlockedCell(grid_id=grid.id, row_index=row_idx, col_index=col_idx, message="Explorat!")
        db.session.add(new_cell)
        db.session.commit()
        return jsonify({'status': 'unlocked', 'row': row_idx, 'col': col_idx})
    
    return jsonify({'status': 'already_visited', 'row': row_idx, 'col': col_idx})

# Task 3 & 7: Logică spațială și returnare date grid [cite: 74, 78]
@main.route('/api/grid/<int:grid_id>', methods=['GET'])
def get_grid_progress(grid_id):
    # Returnăm celulele deblocate pentru a fi desenate pe hartă
    unlocked = UnlockedCell.query.filter_by(grid_id=grid_id).all()
    results = []
    for cell in unlocked:
        results.append({
            'row': cell.row_index,
            'col': cell.col_index,
            'msg': cell.message
        })
    return jsonify(results)