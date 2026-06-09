"""
异动监控模块测试
"""
import pytest
from morning.anomaly_monitor import AnomalyMonitor, AnomalyResult


class TestAnomalyMonitor:
    """异动监控器测试"""

    @pytest.fixture
    def monitor(self):
        """创建异动监控器"""
        return AnomalyMonitor({"push_threshold": 60})

    def test_monitor_macro(self, monitor):
        """测试宏观经济监控"""
        score = monitor.monitor_macro()
        assert score.dimension == "宏观"
        assert 0 <= score.score <= 25

    def test_monitor_commodity(self, monitor):
        """测试大宗商品监控"""
        score = monitor.monitor_commodity()
        assert score.dimension == "大宗"
        assert 0 <= score.score <= 25

    def test_monitor_tech(self, monitor):
        """测试科技赛道监控"""
        news_list = [
            {"title": "AI技术突破", "text": "人工智能"},
            {"title": "芯片产业发展", "text": "半导体"},
            {"title": "普通新闻", "text": "无关键词"}
        ]
        score = monitor.monitor_tech(news_list)
        assert score.dimension == "科技"
        assert 0 <= score.score <= 25

    def test_monitor_event(self, monitor):
        """测试突发事件监控"""
        news_list = [
            {"title": "政策变化", "text": "新政策"},
            {"title": "地缘政治", "text": "制裁"}
        ]
        score = monitor.monitor_event(news_list)
        assert score.dimension == "突发"
        assert 0 <= score.score <= 25

    def test_run(self, monitor):
        """测试完整运行"""
        result = monitor.run()
        assert isinstance(result, AnomalyResult)
        assert 0 <= result.total_score <= 100
        assert isinstance(result.should_push, bool)

    def test_push_threshold(self):
        """测试推送阈值"""
        monitor = AnomalyMonitor({"push_threshold": 0})
        result = monitor.run()
        assert result.should_push == True

        monitor = AnomalyMonitor({"push_threshold": 100})
        result = monitor.run()
        assert result.should_push == False
