"""
股票复盘工具 - 数据库模型与管理
使用 SQLAlchemy ORM，开发阶段使用 SQLite，可切换 MySQL/PostgreSQL
"""
import json
import logging
from datetime import datetime, date
from sqlalchemy import (
    create_engine, Column, Integer, String, Date, DateTime,
    Float, Boolean, Text, Index, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from config import DB_URI

logger = logging.getLogger(__name__)
Base = declarative_base()


class ReviewDaily(Base):
    """每日复盘主表 - 存储完整 JSON 快照"""
    __tablename__ = "review_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    raw_json = Column(Text, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "trade_date": self.trade_date.isoformat() if self.trade_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "raw_json": json.loads(self.raw_json) if self.raw_json else None,
        }


class SectorMoneyFlow(Base):
    """板块资金流向表"""
    __tablename__ = "sector_money_flow"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False, index=True)
    sector_code = Column(String(20), default="")
    sector_name = Column(String(50), nullable=False)
    flow_type = Column(String(20), nullable=False)  # inflow / outflow / abnormal
    net_amount = Column(Float, default=0.0)          # 净流入/净流出金额(元)
    change_percent = Column(Float, default=0.0)      # 涨跌幅(%)
    turnover_amount = Column(Float, default=0.0)     # 成交额(元)
    rank_no = Column(Integer, default=0)
    extra_json = Column(Text, default="{}")          # 额外数据
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("trade_date", "sector_name", "flow_type", name="uq_sector_flow"),
        Index("idx_sector_date_type", "trade_date", "flow_type"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "trade_date": self.trade_date.isoformat() if self.trade_date else None,
            "sector_code": self.sector_code,
            "sector_name": self.sector_name,
            "flow_type": self.flow_type,
            "net_amount": self.net_amount,
            "change_percent": self.change_percent,
            "turnover_amount": self.turnover_amount,
            "rank_no": self.rank_no,
            "extra_json": json.loads(self.extra_json) if self.extra_json else {},
        }


class StockReviewResult(Base):
    """个股复盘结果表 - 存储所有分类的个股数据"""
    __tablename__ = "stock_review_result"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(Date, nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)
    stock_code = Column(String(10), nullable=False, index=True)
    stock_name = Column(String(20), nullable=False)
    sector_name = Column(String(50), default="")
    net_amount = Column(Float, default=0.0)           # 资金净额(元)
    change_percent = Column(Float, default=0.0)       # 涨跌幅(%)
    turnover_amount = Column(Float, default=0.0)      # 成交额(元)
    volume = Column(Float, default=0.0)               # 成交量(股)
    turnover_rate = Column(Float, default=0.0)        # 换手率(%)
    rank_no = Column(Integer, default=0)
    extra_json = Column(Text, default="{}")           # 额外指标(JSON)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("trade_date", "category", "stock_code", name="uq_stock_review"),
        Index("idx_stock_date_cat", "trade_date", "category"),
        Index("idx_stock_code_date", "stock_code", "trade_date"),
        Index("idx_stock_name", "stock_name"),
        Index("idx_sector_name", "sector_name"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "trade_date": self.trade_date.isoformat() if self.trade_date else None,
            "category": self.category,
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "sector_name": self.sector_name,
            "net_amount": self.net_amount,
            "change_percent": self.change_percent,
            "turnover_amount": self.turnover_amount,
            "volume": self.volume,
            "turnover_rate": self.turnover_rate,
            "rank_no": self.rank_no,
            "extra_json": json.loads(self.extra_json) if self.extra_json else {},
        }


class StockBasicInfo(Base):
    """股票基础信息表 - 用于 ST/新股/次新股过滤"""
    __tablename__ = "stock_basic_info"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(10), nullable=False, unique=True, index=True)
    stock_name = Column(String(20), nullable=False)
    list_date = Column(Date, nullable=True)           # 上市日期
    is_st = Column(Boolean, default=False)
    is_new_stock = Column(Boolean, default=False)
    is_sub_new_stock = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index("idx_basic_st", "is_st"),
        Index("idx_basic_new", "is_new_stock"),
    )

    def to_dict(self):
        return {
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "list_date": self.list_date.isoformat() if self.list_date else None,
            "is_st": self.is_st,
            "is_new_stock": self.is_new_stock,
            "is_sub_new_stock": self.is_sub_new_stock,
        }


class DatabaseManager:
    """数据库管理器 - 封装所有数据库操作"""

    def __init__(self, db_uri: str = None):
        self.engine = create_engine(db_uri or DB_URI, echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        logger.info(f"数据库初始化完成: {db_uri or DB_URI}")

    def get_session(self) -> Session:
        return self.SessionLocal()

    # ===== 写入操作（支持 UPSERT，同一天重复执行覆盖旧数据） =====

    def save_daily_review(self, trade_date: date, raw_json: str):
        """保存每日复盘主记录（覆盖更新）"""
        session = self.get_session()
        try:
            existing = session.query(ReviewDaily).filter_by(trade_date=trade_date).first()
            if existing:
                existing.raw_json = raw_json
                existing.updated_at = datetime.now()
                logger.info(f"更新每日复盘主记录: {trade_date}")
            else:
                record = ReviewDaily(trade_date=trade_date, raw_json=raw_json)
                session.add(record)
                logger.info(f"新增每日复盘主记录: {trade_date}")
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"保存每日复盘主记录失败: {e}")
            raise
        finally:
            session.close()

    def save_sector_flows(self, trade_date: date, records: list, flow_type: str):
        """保存板块资金流向（先删后插，保证幂等）"""
        session = self.get_session()
        try:
            session.query(SectorMoneyFlow).filter_by(
                trade_date=trade_date, flow_type=flow_type
            ).delete()
            for r in records:
                obj = SectorMoneyFlow(
                    trade_date=trade_date,
                    sector_code=r.get("sector_code", ""),
                    sector_name=r.get("sector_name", ""),
                    flow_type=flow_type,
                    net_amount=r.get("net_amount", 0),
                    change_percent=r.get("change_percent", 0),
                    turnover_amount=r.get("turnover_amount", 0),
                    rank_no=r.get("rank_no", 0),
                    extra_json=json.dumps(r.get("extra", {}), ensure_ascii=False),
                )
                session.add(obj)
            session.commit()
            logger.info(f"保存板块资金流向 [{flow_type}] {len(records)} 条: {trade_date}")
        except Exception as e:
            session.rollback()
            logger.error(f"保存板块资金流向失败: {e}")
            raise
        finally:
            session.close()

    def save_stock_results(self, trade_date: date, records: list, category: str):
        """保存个股复盘结果（先删后插，保证幂等）"""
        session = self.get_session()
        try:
            session.query(StockReviewResult).filter_by(
                trade_date=trade_date, category=category
            ).delete()
            for r in records:
                obj = StockReviewResult(
                    trade_date=trade_date,
                    category=category,
                    stock_code=r.get("stock_code", ""),
                    stock_name=r.get("stock_name", ""),
                    sector_name=r.get("sector_name", ""),
                    net_amount=r.get("net_amount", 0),
                    change_percent=r.get("change_percent", 0),
                    turnover_amount=r.get("turnover_amount", 0),
                    volume=r.get("volume", 0),
                    turnover_rate=r.get("turnover_rate", 0),
                    rank_no=r.get("rank_no", 0),
                    extra_json=json.dumps(r.get("extra", {}), ensure_ascii=False),
                )
                session.add(obj)
            session.commit()
            logger.info(f"保存个股结果 [{category}] {len(records)} 条: {trade_date}")
        except Exception as e:
            session.rollback()
            logger.error(f"保存个股结果失败: {e}")
            raise
        finally:
            session.close()

    def save_stock_basic_infos(self, records: list):
        """批量保存/更新股票基础信息"""
        session = self.get_session()
        try:
            for r in records:
                existing = session.query(StockBasicInfo).filter_by(
                    stock_code=r["stock_code"]
                ).first()
                if existing:
                    existing.stock_name = r.get("stock_name", existing.stock_name)
                    existing.list_date = r.get("list_date", existing.list_date)
                    existing.is_st = r.get("is_st", existing.is_st)
                    existing.is_new_stock = r.get("is_new_stock", existing.is_new_stock)
                    existing.is_sub_new_stock = r.get("is_sub_new_stock", existing.is_sub_new_stock)
                    existing.updated_at = datetime.now()
                else:
                    obj = StockBasicInfo(
                        stock_code=r["stock_code"],
                        stock_name=r.get("stock_name", ""),
                        list_date=r.get("list_date"),
                        is_st=r.get("is_st", False),
                        is_new_stock=r.get("is_new_stock", False),
                        is_sub_new_stock=r.get("is_sub_new_stock", False),
                    )
                    session.add(obj)
            session.commit()
            logger.info(f"保存股票基础信息 {len(records)} 条")
        except Exception as e:
            session.rollback()
            logger.error(f"保存股票基础信息失败: {e}")
            raise
        finally:
            session.close()

    # ===== 查询操作 =====

    def query_daily_review(self, trade_date: date):
        """查询某天的完整复盘"""
        session = self.get_session()
        try:
            record = session.query(ReviewDaily).filter_by(trade_date=trade_date).first()
            return record.to_dict() if record else None
        finally:
            session.close()

    def query_sector_flows(self, trade_date: date = None, flow_type: str = None,
                           sector_name: str = None, page: int = 1, page_size: int = 20):
        """查询板块资金流向"""
        session = self.get_session()
        try:
            q = session.query(SectorMoneyFlow)
            if trade_date:
                q = q.filter(SectorMoneyFlow.trade_date == trade_date)
            if flow_type:
                q = q.filter(SectorMoneyFlow.flow_type == flow_type)
            if sector_name:
                q = q.filter(SectorMoneyFlow.sector_name.like(f"%{sector_name}%"))
            total = q.count()
            records = q.order_by(SectorMoneyFlow.trade_date.desc(), SectorMoneyFlow.rank_no) \
                       .offset((page - 1) * page_size).limit(page_size).all()
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "data": [r.to_dict() for r in records],
            }
        finally:
            session.close()

    def query_stock_results(self, trade_date: date = None, category: str = None,
                            stock_code: str = None, stock_name: str = None,
                            sector_name: str = None, page: int = 1, page_size: int = 20):
        """查询个股复盘结果（支持多维度筛选 + 分页）"""
        session = self.get_session()
        try:
            q = session.query(StockReviewResult)
            if trade_date:
                q = q.filter(StockReviewResult.trade_date == trade_date)
            if category:
                q = q.filter(StockReviewResult.category == category)
            if stock_code:
                q = q.filter(StockReviewResult.stock_code == stock_code)
            if stock_name:
                q = q.filter(StockReviewResult.stock_name.like(f"%{stock_name}%"))
            if sector_name:
                q = q.filter(StockReviewResult.sector_name.like(f"%{sector_name}%"))
            total = q.count()
            records = q.order_by(StockReviewResult.trade_date.desc(), StockReviewResult.rank_no) \
                       .offset((page - 1) * page_size).limit(page_size).all()
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "data": [r.to_dict() for r in records],
            }
        finally:
            session.close()

    def query_stock_history(self, stock_code: str, page: int = 1, page_size: int = 20):
        """查询某只股票的历史入选记录"""
        session = self.get_session()
        try:
            q = session.query(StockReviewResult).filter_by(stock_code=stock_code)
            total = q.count()
            records = q.order_by(StockReviewResult.trade_date.desc()) \
                       .offset((page - 1) * page_size).limit(page_size).all()
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "data": [r.to_dict() for r in records],
            }
        finally:
            session.close()

    def get_excluded_codes(self) -> set:
        """获取应排除的股票代码集合（ST + 新股 + 次新股）"""
        session = self.get_session()
        try:
            records = session.query(StockBasicInfo.stock_code).filter(
                (StockBasicInfo.is_st == True) |
                (StockBasicInfo.is_new_stock == True) |
                (StockBasicInfo.is_sub_new_stock == True)
            ).all()
            return {r[0] for r in records}
        finally:
            session.close()
