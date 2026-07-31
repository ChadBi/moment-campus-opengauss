"""Test openGauss 7.0.0-RC3 vector extension support"""
import asyncio
import asyncpg

async def test():
    conn = await asyncpg.connect(
        host='localhost', port=5432,
        user='gaussdb', password='Gaussdb@123',
        database='moment_campus',
    )
    print('1. Connection OK')
    
    # Test 1: Create extension
    try:
        await conn.execute('CREATE EXTENSION IF NOT EXISTS vector')
        print('2. CREATE EXTENSION vector OK')
    except Exception as e:
        print(f'2. CREATE EXTENSION vector FAILED: {e}')
    
    # Test 2: Check if extension exists
    try:
        rows = await conn.fetch("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        print(f'3. Extension exists: {len(rows) > 0}')
    except Exception as e:
        print(f'3. Check extension FAILED: {e}')
    
    # Test 3: Create test table with vector column
    try:
        await conn.execute('DROP TABLE IF EXISTS _vec_test')
        await conn.execute('CREATE TABLE _vec_test (id SERIAL, data vector(384))')
        print('4. CREATE TABLE with vector OK')
    except Exception as e:
        print(f'4. CREATE TABLE FAILED: {e}')
    
    # Test 4: Insert vector data
    try:
        await conn.execute(
            "INSERT INTO _vec_test (data) VALUES "
            "(array_fill(0.1, ARRAY[384])::vector(384))"
        )
        print('5. INSERT vector OK')
    except Exception as e:
        print(f'5. INSERT FAILED: {e}')
    
    # Test 5: Vector similarity search
    try:
        rows = await conn.fetch(
            "SELECT id FROM _vec_test "
            "ORDER BY data <=> array_fill(0.2, ARRAY[384])::vector(384) "
            "LIMIT 1"
        )
        print(f'6. Vector similarity search OK: found {len(rows)} rows')
    except Exception as e:
        print(f'6. Vector search FAILED: {e}')
    
    # Test 6: Create HNSW index
    try:
        await conn.execute(
            'CREATE INDEX idx_vec_test ON _vec_test '
            'USING hnsw (data vector_l2_ops)'
        )
        print('7. HNSW index OK')
    except Exception as e:
        print(f'7. HNSW index FAILED: {e}')
    
    # Cleanup
    try:
        await conn.execute('DROP TABLE _vec_test')
        print('8. Cleanup OK')
    except Exception as e:
        print(f'8. Cleanup FAILED: {e}')
    
    await conn.close()
    print('\n=== Test Complete ===')

asyncio.run(test())