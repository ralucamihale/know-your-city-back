from flask import Blueprint, request, jsonify
from .extensions import db
from .models import User, Grid, UnlockedCell
from werkzeug.security import generate_password_hash, check_password_hash
from geoalchemy2.elements import WKTElement  # <--- IMPORT NOU
import jwt
import datetime
import math

main = Blueprint('main', __name__)
SECRET_KEY = "cheie_secreta_pentru_proiect_isi" # Schimbati in productie

# Task 2: Management utilizatori (Register/Login) [cite: 73]
@main.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'Email already exists'}), 400
        
    hashed_pw = generate_password_hash(data['password'])
    new_user = User(email=data['email'], password_hash=hashed_pw)
    db.session.add(new_user)
    db.session.commit()
    
    # NOTA: Am scos crearea automata a grid-ului de aici.
    # Acum grid-ul se face manual prin butonul din aplicatie.

    return jsonify({'message': 'User created successfully'}), 201

@main.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data['email']).first()
    
    if not user or not check_password_hash(user.password_hash, data['password']):
        return jsonify({'message': 'Login failed'}), 401
    
    # Returnam si user_id ca sa stie frontend-ul cine esti
    token = jwt.encode({
        'user_id': str(user.id),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, SECRET_KEY, algorithm="HS256")
    
    return jsonify({'token': token, 'user_id': str(user.id)})

@main.route('/api/create_grid', methods=['POST'])
def create_game_grid():
    data = request.get_json()
    user_id = data.get('user_id')
    lat = data.get('lat')
    lng = data.get('lng')
    # Parametru opțional: dacă e True, șterge gridul vechi. Dacă e False, îl păstrează.
    force_reset = data.get('force_reset', True) 

    if not user_id or not lat or not lng:
        return jsonify({'message': 'Missing data'}), 400

    # 1. Verificăm dacă există deja un grid
    existing_grid = Grid.query.filter_by(user_id=user_id).first()

    if existing_grid and not force_reset:
        # Dacă există și NU vrem reset, returnăm gridul existent fără să facem nimic
        return jsonify({
            'message': 'Grid already exists', 
            'grid_id': existing_grid.id,
            'status': 'loaded_existing'
        })

    # 2. Dacă vrem să recreăm (sau nu există), ștergem tot ce e vechi
    if existing_grid:
        # PAS CRITIC: Ștergem întâi celulele dependente (Foreign Key Fix)
        UnlockedCell.query.filter_by(grid_id=existing_grid.id).delete()
        # Apoi ștergem grid-ul
        db.session.delete(existing_grid)
        db.session.commit()

    # 3. Creăm noul grid
    center_wkt = f'POINT({lng} {lat})'
    
    new_grid = Grid(
        user_id=user_id,
        center_point=WKTElement(center_wkt, srid=4326),
        slot_number=1,
        dimension=9,         
        cell_size_meters=100 
    )
    
    db.session.add(new_grid)
    db.session.flush() # Obținem ID-ul

    # Deblocăm celula de start (0,0)
    start_cell = UnlockedCell(
        grid_id=new_grid.id,
        row_index=0,
        col_index=0,
        message="Start Point"
    )
    db.session.add(start_cell)
    
    db.session.commit()

    return jsonify({'message': 'Grid created!', 'grid_id': new_grid.id, 'status': 'created_new'})

@main.route('/api/explore', methods=['POST'])
def explore_cell():
    data = request.get_json()
    user_lat = data.get('lat')
    user_lng = data.get('lng')
    user_id = data.get('user_id')
    
    grid = Grid.query.filter_by(user_id=user_id).first()
    if not grid:
        return jsonify({'status': 'no_grid'})

    # Luam centrul folosind functii PostGIS sau aproximare
    # Aici facem query in DB pentru a lua coordonatele centrului
    # Nota: Pentru MVP simplificam si recalculam distantele in Python
    # Dar trebuie sa stim centrul. 
    # Deoarece citirea WKT e complexa direct, vom returna 'unlocked' doar daca gridul exista
    # Ideal aici ar trebui o logica mai robusta de extragere a punctului din DB.
    
    # SIMPLIFICARE PENTRU MVP (Fara interogare complexa de geometrie):
    # Presupunem ca frontend-ul redeseneaza gridul si calculam relativ la ce stim.
    # Pentru a face asta corect in backend, avem nevoie de coordonatele centrului:
    
    # Varianta Robustă PostGIS:
    # SQL: ST_X(center_point), ST_Y(center_point)
    center_query = db.session.query(
        db.func.ST_X(grid.center_point), 
        db.func.ST_Y(grid.center_point)
    ).first()
    
    center_lng = center_query[0]
    center_lat = center_query[1]
    
    cell_size = grid.cell_size_meters

    # Calcule matematice (Aproximare metri)
    delta_lat_m = (user_lat - center_lat) * 111320
    delta_lng_m = (user_lng - center_lng) * (40075000 * math.cos(math.radians(center_lat)) / 360)

    row_idx = math.floor(delta_lat_m / cell_size)
    col_idx = math.floor(delta_lng_m / cell_size)

    limit = grid.dimension // 2
    
    # Verificam daca e in grid
    if abs(row_idx) > limit or abs(col_idx) > limit:
        return jsonify({'status': 'out_of_bounds'})

    existing = UnlockedCell.query.filter_by(grid_id=grid.id, row_index=row_idx, col_index=col_idx).first()
    
    if not existing:
        new_cell = UnlockedCell(grid_id=grid.id, row_index=row_idx, col_index=col_idx, message="Explorat!")
        db.session.add(new_cell)
        db.session.commit()
        return jsonify({'status': 'unlocked', 'row': row_idx, 'col': col_idx})
    
    return jsonify({'status': 'already_visited', 'row': row_idx, 'col': col_idx})

@main.route('/api/grid_by_user/<user_id>', methods=['GET'])
def get_grid_by_user(user_id):
    # Endpoint nou pentru a lua gridul userului curent
    grid = Grid.query.filter_by(user_id=user_id).first()
    if not grid:
        return jsonify({'has_grid': False})
        
    # Luam si celulele deblocate
    cells = UnlockedCell.query.filter_by(grid_id=grid.id).all()
    unlocked_data = [{'row': c.row_index, 'col': c.col_index} for c in cells]
    
    # Luam centrul
    center_query = db.session.query(
        db.func.ST_X(grid.center_point), 
        db.func.ST_Y(grid.center_point)
    ).first()
    
    return jsonify({
        'has_grid': True,
        'grid_id': grid.id,
        'center_lat': center_query[1],
        'center_lng': center_query[0],
        'dimension': grid.dimension,
        'cell_size': grid.cell_size_meters,
        'unlocked_cells': unlocked_data
    })

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