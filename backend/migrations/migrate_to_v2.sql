-- ============================================
-- 数据库迁移脚本：统一前后端数据模型
-- 版本: v1.0 -> v2.0
-- 数据库: SQLite
-- ============================================

-- 步骤 1: 备份数据
-- 在执行迁移前，请手动备份 rent_management.db 文件

-- ============================================
-- 步骤 2: 修改 users 表
-- ============================================

-- 添加新字段
ALTER TABLE users ADD COLUMN full_name VARCHAR(100);
ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'landlord';
ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1;
ALTER TABLE users ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- 创建索引
CREATE INDEX idx_user_role ON users(role);

-- 初始化 role 字段（已有用户设为 landlord）
UPDATE users SET role = 'landlord' WHERE role IS NULL;

-- ============================================
-- 步骤 3: 重构 rooms 表（保留旧数据）
-- ============================================

-- 创建新的 rooms 表
CREATE TABLE rooms_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_number VARCHAR(50) UNIQUE NOT NULL,
    building VARCHAR(50),
    floor INTEGER,
    area DECIMAL(10, 2),
    monthly_rent DECIMAL(10, 2) NOT NULL,
    deposit_amount DECIMAL(10, 2),
    payment_cycle INTEGER DEFAULT 1 NOT NULL,
    status VARCHAR(20) DEFAULT 'available' NOT NULL,
    tenant_name VARCHAR(100),
    tenant_phone VARCHAR(20),
    lease_start DATE,
    lease_end DATE,
    last_payment_date DATE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CHECK (lease_end > lease_start)
);

-- 从旧表迁移数据（name -> room_number）
INSERT INTO rooms_new (
    id, room_number, monthly_rent, tenant_name, tenant_phone,
    lease_start, lease_end, payment_cycle, last_payment_date,
    created_at, status, description
)
SELECT
    id,
    name AS room_number,
    monthly_rent,
    tenant_name,
    tenant_phone,
    lease_start,
    lease_end,
    payment_cycle,
    last_payment_date,
    created_at,
    'available' AS status,  -- 默认状态
    NULL AS description
FROM rooms;

-- 创建索引
CREATE INDEX idx_room_number ON rooms_new(room_number);
CREATE INDEX idx_room_status ON rooms_new(status);
CREATE INDEX idx_room_tenant ON rooms_new(tenant_name);

-- 删除旧表并重命名新表
DROP TABLE rooms;
ALTER TABLE rooms_new RENAME TO rooms;

-- ============================================
-- 步骤 4: 修改 payments 表
-- ============================================

-- 添加新字段
ALTER TABLE payments ADD COLUMN payment_type VARCHAR(20) DEFAULT 'rent';
ALTER TABLE payments ADD COLUMN due_date DATE;
ALTER TABLE payments ADD COLUMN status VARCHAR(20) DEFAULT 'completed';
ALTER TABLE payments ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- 创建索引
CREATE INDEX idx_payment_room_date ON payments(room_id, payment_date);
CREATE INDEX idx_payment_type ON payments(payment_type);
CREATE INDEX idx_payment_status ON payments(status);

-- 初始化 payment_type 字段
UPDATE payments SET payment_type = 'rent' WHERE payment_type IS NULL;
UPDATE payments SET status = 'completed' WHERE status IS NULL;

-- ============================================
-- 步骤 5: 修改 utility_readings 表
-- ============================================

-- 添加新字段
ALTER TABLE utility_readings ADD COLUMN previous_reading DECIMAL(10, 2);
ALTER TABLE utility_readings ADD COLUMN usage DECIMAL(10, 2);
ALTER TABLE utility_readings ADD COLUMN amount DECIMAL(10, 2);
ALTER TABLE utility_readings ADD COLUMN rate_used DECIMAL(10, 4);
ALTER TABLE utility_readings ADD COLUMN recorded_by INTEGER;
ALTER TABLE utility_readings ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- 更新约束（支持 gas）
-- SQLite 不支持直接修改约束，需要重建表
CREATE TABLE utility_readings_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id INTEGER NOT NULL,
    utility_type VARCHAR(10) NOT NULL,
    reading DECIMAL(10, 2) NOT NULL,
    reading_date DATE NOT NULL,
    previous_reading DECIMAL(10, 2),
    usage DECIMAL(10, 2),
    amount DECIMAL(10, 2),
    rate_used DECIMAL(10, 4),
    recorded_by INTEGER,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CHECK (utility_type IN ('water', 'electricity', 'gas')),
    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
    FOREIGN KEY (recorded_by) REFERENCES users(id) ON DELETE SET NULL
);

-- 迁移数据（note -> notes）
INSERT INTO utility_readings_new (
    id, room_id, utility_type, reading, reading_date,
    previous_reading, usage, amount, rate_used,
    notes, created_at
)
SELECT
    id, room_id, utility_type, reading, reading_date,
    NULL AS previous_reading,
    NULL AS usage,
    NULL AS amount,
    NULL AS rate_used,
    note AS notes,
    created_at
FROM utility_readings;

-- 创建索引
CREATE INDEX idx_reading_room_type_date ON utility_readings_new(room_id, utility_type, reading_date);
CREATE INDEX idx_reading_date ON utility_readings_new(reading_date);
CREATE INDEX idx_reading_type ON utility_readings_new(utility_type);

-- 删除旧表并重命名
DROP TABLE utility_readings;
ALTER TABLE utility_readings_new RENAME TO utility_readings;

-- ============================================
-- 步骤 6: 修改 utility_rates 表
-- ============================================

-- 重命名字段
ALTER TABLE utility_rates RENAME COLUMN unit_price TO rate_per_unit;

-- 添加新字段
ALTER TABLE utility_rates ADD COLUMN is_active BOOLEAN DEFAULT 1;
ALTER TABLE utility_rates ADD COLUMN description TEXT;
ALTER TABLE utility_rates ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- 删除旧的 unique 约束（SQLite 需要重建表）
CREATE TABLE utility_rates_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    utility_type VARCHAR(10) NOT NULL,
    rate_per_unit DECIMAL(10, 4) NOT NULL,
    effective_date DATE NOT NULL,
    is_active BOOLEAN DEFAULT 1 NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CHECK (utility_type IN ('water', 'electricity', 'gas'))
);

-- 迁移数据
INSERT INTO utility_rates_new (
    id, utility_type, rate_per_unit, effective_date,
    is_active, description, created_at
)
SELECT
    id, utility_type, rate_per_unit, effective_date,
    1 AS is_active,
    NULL AS description,
    created_at
FROM utility_rates;

-- 创建索引
CREATE INDEX idx_rate_type_date ON utility_rates_new(utility_type, effective_date);
CREATE INDEX idx_rate_type ON utility_rates_new(utility_type);

-- 删除旧表并重命名
DROP TABLE utility_rates;
ALTER TABLE utility_rates_new RENAME TO utility_rates;

-- ============================================
-- 步骤 7: 初始化数据
-- ============================================

-- 初始化水电费率（如果不存在）
INSERT INTO utility_rates (utility_type, rate_per_unit, effective_date, description, is_active)
SELECT 'water', 5.0, date('now'), '默认水费率（5元/吨）', 1
WHERE NOT EXISTS (SELECT 1 FROM utility_rates WHERE utility_type = 'water');

INSERT INTO utility_rates (utility_type, rate_per_unit, effective_date, description, is_active)
SELECT 'electricity', 1.0, date('now'), '默认电费率（1元/度）', 1
WHERE NOT EXISTS (SELECT 1 FROM utility_rates WHERE utility_type = 'electricity');

-- ============================================
-- 迁移完成提示
-- ============================================

-- 验证迁移结果
SELECT 'Users:' as table_name, COUNT(*) as count FROM users
UNION ALL
SELECT 'Rooms:', COUNT(*) FROM rooms
UNION ALL
SELECT 'Payments:', COUNT(*) FROM payments
UNION ALL
SELECT 'Utility Readings:', COUNT(*) FROM utility_readings
UNION ALL
SELECT 'Utility Rates:', COUNT(*) FROM utility_rates;
