"""
策略参数进化器
使用 DEAP 库的遗传算法搜索最优策略参数组合

优化参数维度：
  - 评分阈值：min_score (10-30)
  - 买入参数：封板时间截止、最小封单比、最小换手率
  - 卖出参数：止盈、止损、回落止盈
  - 仓位参数：每日最大买入数、单票占比

适应度 = 年化收益 x 0.5 + 夏普比率 x 0.3 - 最大回撤 x 0.2
"""
import copy
import json
import logging
import random
from datetime import datetime
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------- 参数边界定义 ----------

PARAM_BOUNDS = {
    # 打板评分阈值
    "min_score": (8, 28, int),
    # 买入时间截止（分钟偏移 9:30）
    "buy_timeout_minutes": (30, 90, int),  # 10:00 ~ 11:00
    # 最小封单额/成交额比
    "min_seal_ratio": (0.02, 0.20, float),
    # 最小换手率 %
    "turnover_min": (1.0, 8.0, float),
    # 最大换手率 %
    "turnover_max": (15.0, 35.0, float),
    # 最小流通市值 (亿)
    "market_cap_min": (10, 50, int),
    # 止盈 %
    "profit_target": (0.03, 0.12, float),
    # 止损 %
    "stop_loss": (-0.08, -0.02, float),
    # 回落止盈 %
    "trailing_stop": (0.01, 0.05, float),
    # 每日最大买入数
    "max_daily_buy": (1, 5, int),
    # 单票仓位占比
    "single_pct": (0.05, 0.25, float),
}


def _random_individual() -> list:
    """生成随机个体（在边界内均匀采样）"""
    ind = []
    for name, (lo, hi, dtype) in PARAM_BOUNDS.items():
        if dtype == int:
            val = random.randint(lo, hi)
        else:
            val = random.uniform(lo, hi)
            val = round(val, 4)
        ind.append(val)
    return ind


def _individual_to_dict(ind: list) -> dict:
    """将个体列表转换为参数字典"""
    keys = list(PARAM_BOUNDS.keys())
    types = [v[2] for v in PARAM_BOUNDS.values()]
    return {
        k: types[i](ind[i]) if types[i] == int else round(float(ind[i]), 4)
        for i, k in enumerate(keys)
    }


# ============================================================
# 遗传算法进化器
# ============================================================

class StrategyEvolver:
    """
    策略参数进化器

    用法：
        evolver = StrategyEvolver(config={
            "population_size": 30,
            "generations": 20,
        }, evaluator=my_eval_func)

        best_params = evolver.evolve()
    """

    def __init__(
        self,
        config: Optional[dict] = None,
        evaluator=None,
    ):
        """
        Args:
            config: 进化参数配置字典
                population_size: 种群大小（默认30）
                generations: 进化代数（默认20）
                elite_ratio: 精英保留比例（默认0.2）
                crossover_prob: 交叉概率（默认0.7）
                mutation_prob: 变异概率（默认0.1）
            evaluator: 适应度评估函数
                签名：func(params_dict) -> (annual_return, sharpe_ratio, max_drawdown)
                如果为 None，则使用默认的 mock 评估器（仅用于测试）
        """
        cfg = config or {}
        self.pop_size = int(cfg.get("population_size", 30))
        self.generations = int(cfg.get("generations", 20))
        self.elite_ratio = float(cfg.get("elite_ratio", 0.2))
        self.crossover_prob = float(cfg.get("crossover_prob", 0.7))
        self.mutation_prob = float(cfg.get("mutation_prob", 0.1))
        self.fitness_weights = cfg.get("fitness_weights", {
            "annual_return": 0.5,
            "sharpe_ratio": 0.3,
            "max_drawdown": -0.2,
        })

        # 适应度函数
        self._evaluator = evaluator or self._mock_evaluate

        # 记录进化历史
        self.history = {
            "generation": [],
            "best_fitness": [],
            "avg_fitness": [],
            "best_params": [],
        }

    # ---- 适应度评估 ----

    def _mock_evaluate(self, params: dict) -> tuple:
        """
        默认的 mock 评估函数，仅用于导入测试
        实际使用时需传入真实 evaluator
        """
        score = params.get("min_score", 14) / 28 * 0.5
        return (score, 1.0, -0.15)

    def _compute_fitness(self, params: dict) -> float:
        """
        从评估结果计算适应度

        Returns:
            fitness: 综合适应度（越高越好）
        """
        try:
            annual_return, sharpe, max_dd = self._evaluator(params)
        except Exception as e:
            logger.warning(f"参数评估失败: {e}")
            return -999.0

        fitness = (
            self.fitness_weights.get("annual_return", 0.5) * annual_return
            + self.fitness_weights.get("sharpe_ratio", 0.3) * sharpe
            + self.fitness_weights.get("max_drawdown", -0.2) * max_dd
        )
        return fitness

    # ---- 进化算法核心 ----

    def _init_population(self) -> list:
        """初始化种群"""
        return [_random_individual() for _ in range(self.pop_size)]

    def _crossover(self, p1: list, p2: list) -> tuple[list, list]:
        """模拟二进制交叉 (SBX)"""
        c1, c2 = p1[:], p2[:]
        if random.random() < self.crossover_prob:
            for i in range(len(p1)):
                if random.random() < 0.5:
                    c1[i] = p1[i] * 0.5 + p2[i] * 0.5
                    c2[i] = p2[i] * 0.5 + p1[i] * 0.5
                    # 边界裁剪
                    name = list(PARAM_BOUNDS.keys())[i]
                    lo, hi, dtype = PARAM_BOUNDS[name]
                    c1[i] = max(lo, min(hi, c1[i]))
                    c2[i] = max(lo, min(hi, c2[i]))
                    if dtype == int:
                        c1[i] = round(c1[i])
                        c2[i] = round(c2[i])
        return c1, c2

    def _mutate(self, ind: list, rate: Optional[float] = None) -> list:
        """高斯变异"""
        rate = rate or self.mutation_prob
        mutated = ind[:]
        for i in range(len(ind)):
            if random.random() < rate:
                name = list(PARAM_BOUNDS.keys())[i]
                lo, hi, dtype = PARAM_BOUNDS[name]
                # 高斯扰动，std = 区间长度的 10%
                sigma = (hi - lo) * 0.1
                val = ind[i] + random.gauss(0, sigma)
                val = max(lo, min(hi, val))
                mutated[i] = round(val) if dtype == int else round(val, 4)
        return mutated

    def _select(self, population: list, fitnesses: list[float]) -> list:
        """
        锦标赛选择 + 精英保留

        Returns:
            下一代种群
        """
        # 精英保留
        n_elite = max(1, int(self.pop_size * self.elite_ratio))
        elite_idx = np.argsort(fitnesses)[-n_elite:]
        elites = [population[i] for i in elite_idx]

        # 锦标赛选择填充剩余
        remaining = self.pop_size - n_elite
        offspring = elites[:]
        for _ in range(remaining):
            # 随机选 3 个，取最优
            candidates = random.sample(range(len(population)), min(3, len(population)))
            best_idx = max(candidates, key=lambda i: fitnesses[i])
            offspring.append(population[best_idx][:])

        return offspring

    # ---- 运行入口 ----

    def evolve(self, verbose: bool = True) -> dict:
        """
        运行遗传算法进化

        Args:
            verbose: 是否打印进化日志

        Returns:
            最优参数字典
        """
        pop = self._init_population()
        best_overall = None
        best_fitness_overall = -999

        for gen in range(self.generations):
            # 评估适应度
            fitnesses = [self._compute_fitness(_individual_to_dict(ind)) for ind in pop]

            # 记录
            best_idx = int(np.argmax(fitnesses))
            best_fit = fitnesses[best_idx]
            avg_fit = float(np.mean(fitnesses))
            best_ind = pop[best_idx]

            if best_fit > best_fitness_overall:
                best_fitness_overall = best_fit
                best_overall = best_ind[:]

            self.history["generation"].append(gen + 1)
            self.history["best_fitness"].append(best_fit)
            self.history["avg_fitness"].append(avg_fit)
            self.history["best_params"].append(_individual_to_dict(best_ind))

            if verbose:
                logger.info(
                    "Gen %2d/%d | best=%+.4f avg=%+.4f | params=%s",
                    gen + 1, self.generations, best_fit, avg_fit,
                    _individual_to_dict(best_ind),
                )

            # 选择 & 繁殖
            pop = self._select(pop, fitnesses)
            next_pop = []
            i = 0
            while i < len(pop):
                if i + 1 < len(pop):
                    c1, c2 = self._crossover(pop[i], pop[i + 1])
                    next_pop.append(self._mutate(c1))
                    next_pop.append(self._mutate(c2))
                    i += 2
                else:
                    next_pop.append(self._mutate(pop[i]))
                    i += 1
            pop = next_pop[:self.pop_size]

        if best_overall is None:
            # fallback
            return _individual_to_dict(pop[0]) if pop else {}

        return _individual_to_dict(best_overall)

    def generate_report(self, best_params: dict) -> str:
        """
        生成文本报告

        Args:
            best_params: 最优参数字典

        Returns:
            格式化的 Markdown 报告
        """
        lines = [
            "## 策略参数进化报告",
            "",
            f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "### 进化参数",
            "",
            f"- 种群大小：{self.pop_size}",
            f"- 进化代数：{self.generations}",
            f"- 交叉概率：{self.crossover_prob}",
            f"- 变异概率：{self.mutation_prob}",
            f"- 精英保留：{self.elite_ratio}",
            "",
            "### 最优参数",
            "",
            "| 参数 | 值 |",
            "|------|:---:|",
        ]

        for key, val in best_params.items():
            lines.append(f"| {key} | {val} |")

        lines.extend([
            "",
            "### 进化曲线摘要",
            "",
        ])
        if self.history["best_fitness"]:
            best_gen = self.history["generation"][-1]
            best_f = self.history["best_fitness"][-1]
            lines.append(f"- 末代最优适应度：{best_f:.4f}（第 {best_gen} 代）")
            lines.append(f"- 末代平均适应度：{self.history['avg_fitness'][-1]:.4f}")
            if len(self.history["best_fitness"]) > 1:
                first_f = self.history["best_fitness"][0]
                lines.append(f"- 适应度提升：{first_f:.4f} → {best_f:.4f}（{best_f - first_f:+.4f}）")

        lines.append("")
        return "\n".join(lines)
