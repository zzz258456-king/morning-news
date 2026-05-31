"""
策略插件接口
所有策略继承 BaseStrategy，实现 run() 方法即可热插拔

添加新策略只需：
    class MyStrategy(BaseStrategy):
        @property
        def name(self): return "我的策略"

        def run(self, ...):
            # 实现回测逻辑
            return engine
"""
from abc import ABC, abstractmethod
from typing import Optional

from .backtest_engine import BacktestEngine


class BaseStrategy(ABC):
    """策略基类 — 所有策略必须实现的接口"""

    def __init__(self, initial_capital: float = 1_000_000):
        self.engine = BacktestEngine(initial_capital=initial_capital)
        self._params: dict = {}

    @property
    @abstractmethod
    def name(self) -> str:
        """策略名称（展示用）"""
        ...

    @property
    def description(self) -> str:
        """策略描述"""
        return ""

    @abstractmethod
    def run(self, **kwargs) -> BacktestEngine:
        """
        运行回测，返回已执行的 BacktestEngine
        子类必须实现此方法
        """
        ...

    def set_params(self, **params):
        """设置策略参数"""
        self._params.update(params)

    def get_param(self, key: str, default=None):
        return self._params.get(key, default)

    def get_params_desc(self) -> list[dict]:
        """
        返回参数描述列表，用于UI自动生成配置面板
        每个元素: {"key": str, "label": str, "type": "int|float|str|bool",
                   "default": any, "min": any, "max": any}
        """
        return []

    @property
    def result(self) -> Optional[dict]:
        """获取回测结果摘要"""
        if not hasattr(self, '_result') or self._result is None:
            return None
        r = self._result
        return {
            "总收益%": r.total_return,
            "年化收益%": r.annual_return,
            "最大回撤%": r.max_drawdown,
            "夏普比率": r.sharpe_ratio,
            "胜率%": r.win_rate,
            "交易次数": r.total_trades,
            "盈亏比": r.profit_loss_ratio,
            "最终权益": self.engine.equity,
        }


def register_strategy(strategy_class) -> None:
    """
    注册策略到全局策略工厂
    用法: @register_strategy 或 register_strategy(MyStrategy)
    """
    StrategyFactory.register(strategy_class)


class StrategyFactory:
    """策略工厂 — 管理所有可用策略"""
    _strategies: dict[str, type] = {}

    @classmethod
    def register(cls, strategy_class: type):
        """注册策略类"""
        name = strategy_class.name if isinstance(strategy_class.name, str) else strategy_class.__name__
        # 实例化获取名称
        try:
            inst = strategy_class()
            name = inst.name
        except Exception:
            name = strategy_class.__name__.replace("Strategy", "")
        cls._strategies[name] = strategy_class
        return strategy_class

    @classmethod
    def create(cls, name: str, **params) -> BaseStrategy:
        """创建策略实例"""
        if name not in cls._strategies:
            raise KeyError(f"未知策略: {name}，可用: {list(cls._strategies.keys())}")
        # 提取构造函数参数
        init_capital = params.pop("initial_capital", None)
        if init_capital is not None:
            inst = cls._strategies[name](initial_capital=init_capital)
        else:
            inst = cls._strategies[name]()
        inst.set_params(**params)
        return inst

    @classmethod
    def list_strategies(cls) -> list[str]:
        """列出所有已注册策略"""
        return list(cls._strategies.keys())

    @classmethod
    def get_strategy_info(cls, name: str) -> dict:
        """获取策略信息"""
        if name not in cls._strategies:
            return {}
        inst = cls._strategies[name]()
        return {
            "name": inst.name,
            "description": inst.description,
            "params": inst.get_params_desc(),
        }
