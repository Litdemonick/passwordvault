from sqlalchemy.orm import sessionmaker
from password_vault.db import Base, build_engine, Entry, Setting

def test_create_tables_and_insert(tmp_path):
    url = f"sqlite:///{tmp_path}/test.db"
    engine = build_engine(url)
    (Base.metadata.create_all)(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    with Session() as s:
        # Inserta un setting
        st = Setting(kdf_salt=b"1234567890123456", verifier=b"abc")
        s.add(st)
        # Inserta una entrada (en real, password_encrypted va cifrada)
        e = Entry(
            title="GitHub",
            username="carlos",
            url="https://github.com",
            notes="",
            password_encrypted=b"x"
        )
        s.add(e)
        s.commit()

    with Session() as s:
        assert s.query(Setting).count() == 1
        assert s.query(Entry).count() == 1
