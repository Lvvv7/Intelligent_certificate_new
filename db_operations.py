#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动建库 + 建表
运行前: pip install sqlalchemy pymysql
"""
import os
import configparser
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base   # 2.0 正式位置
from sqlalchemy import Column, BigInteger, String, DateTime, Integer
from datetime import datetime

Base = declarative_base()

class IntelligentCertification(Base):
    __tablename__ = 'intelligent_certification'

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='主键')
    name = Column(String(255), comment='打证事项名称')
    status = Column(Integer, comment='状态(0:成功,1:失败)')
    creation_date = Column(DateTime, default=datetime.now, comment='创建时间')
    created_by = Column(BigInteger, comment='创建人ID')
    updation_date = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    updated_by = Column(BigInteger, comment='更新人ID')
    enabled_flag = Column(Integer, default=1, comment='是否删除,0 删除 1 未删除')
    trace_id = Column(String(255), comment='trace_id')
    user_account = Column(String(255), comment='用户账号')
    type = Column(String(255), comment='用户类型')
    error_msg = Column(String(255), comment='错误信息')

# ---------- 读取配置 ----------
def get_db_conf():
    cfg = configparser.ConfigParser()
    ini = os.path.join(os.path.dirname(__file__), 'config.ini')
    if os.path.exists(ini):
        cfg.read(ini, encoding='utf-8')
    host = cfg.get('DATABASE', 'HOST', fallback='127.0.0.1')
    port = cfg.getint('DATABASE', 'PORT', fallback=3306)
    user = cfg.get('DATABASE', 'USER', fallback='root')
    pwd  = cfg.get('DATABASE', 'PASSWORD', fallback='root')
    db   = cfg.get('DATABASE', 'NAME', fallback='aigov_gxq_manage')
    return host, port, user, pwd, db

# ---------- 主逻辑 ----------
def main():
    host, port, user, pwd, dbname = get_db_conf()

    # 1. 连接 MySQL 服务器（不指定库）
    server_url = f"mysql+pymysql://{user}:{pwd}@{host}:{port}/?charset=utf8mb3"
    server_eng = create_engine(server_url, echo=False)

    with server_eng.connect() as conn:
        # 2. 建库（若不存在）
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{dbname}` CHARACTER SET utf8mb3;"))
        conn.commit()
        print(f"数据库 `{dbname}` 已确保存在.")

    # 3. 连接目标库并建表
    db_url = f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{dbname}?charset=utf8mb3"
    db_eng = create_engine(db_url, echo=False)
    Base.metadata.create_all(bind=db_eng)
    print(f"表 `{IntelligentCertification.__tablename__}` 创建/更新完成.")

    # 4. 清理
    server_eng.dispose()
    db_eng.dispose()

def add_certification_record(user_account: str, name: str, cert_type: str, 
                           status_code: int, error_types: str = "") -> bool:
    """
    添加证件记录到数据库
    
    Args:
        user_account: 用户账号
        name: 证件名称
        cert_type: 证件类型 ('法人' 或 '个人')
        status_code: 状态码 (0:成功, 1:失败)
        error_types: 错误信息
        
    Returns:
        bool: 是否添加成功
    """
    try:
        host, port, user, pwd, dbname = get_db_conf()
        db_url = f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{dbname}?charset=utf8mb3"
        db_eng = create_engine(db_url, echo=False)
        
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=db_eng)
        session = Session()
        
        # 创建记录
        record = IntelligentCertification(
            name=name,
            status=status_code,
            user_account=user_account,
            type=cert_type,
            error_msg=error_types if error_types else None,
            creation_date=datetime.now(),
            updation_date=datetime.now(),
            enabled_flag=1
        )
        
        session.add(record)
        session.commit()
        session.close()
        db_eng.dispose()
        
        print(f"成功添加证件记录: 用户={user_account}, 证件={name}, 状态={'成功' if status_code == 0 else '失败'}")
        return True
        
    except Exception as e:
        print(f"添加证件记录失败: {str(e)}")
        if 'session' in locals():
            session.rollback()
            session.close()
        if 'db_eng' in locals():
            db_eng.dispose()
        return False

if __name__ == '__main__':
    main()