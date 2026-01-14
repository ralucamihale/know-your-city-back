-- Activăm extensiile necesare (Task 1)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS postgis;

-- Tabela Users [cite: 19]
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    active_grid_id BIGINT, -- Va fi FK după crearea tabelei grids
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabela Grids [cite: 21, 22]
CREATE TABLE grids (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    name VARCHAR(50) DEFAULT 'New Grid',
    slot_number SMALLINT NOT NULL CHECK (slot_number >= 1 AND slot_number <= 3),
    center_point GEOMETRY(POINT, 4326) NOT NULL, -- WGS 84 format
    dimension INTEGER DEFAULT 100,
    cell_size_meters INTEGER DEFAULT 50,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Adăugăm constrângerea FK circulară la users
ALTER TABLE users ADD CONSTRAINT fk_active_grid FOREIGN KEY (active_grid_id) REFERENCES grids(id);

-- Tabela Unlocked_cells [cite: 25]
-- Aceasta folosește o cheie primară compusă (grid_id, row_index, col_index)
CREATE TABLE unlocked_cells (
    grid_id BIGINT REFERENCES grids(id),
    row_index INTEGER NOT NULL,
    col_index INTEGER NOT NULL,
    unlocked_at TIMESTAMPTZ DEFAULT NOW(),
    message VARCHAR(255) DEFAULT NULL,
    PRIMARY KEY (grid_id, row_index, col_index)
);