"""
Flask Web UI 服务器
"""
import os
import sys
import json
import logging
from datetime import date, datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, redirect, url_for

# 添加项目根目录到 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from morning.db_manager import DBManager, TradeRecord
from morning.config import load_config, get_config
from morning.watchlist_manager import WatchlistManager
from morning.trade_journal import TradeJournal
from morning.anomaly_monitor import AnomalyMonitor
from morning.stock_tracker import StockTracker

logger = logging.getLogger(__name__)

app = Flask(__name__,
            template_folder='templates',
            static_folder='static')

# 全局变量
db_manager = None
config = None


def init_app():
    """初始化应用"""
    global db_manager, config

    # 加载配置
    load_config()
    config = get_config()

    # 初始化数据库管理器
    db_manager = DBManager(config.database.daily_path, config.database.global_path)


@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


# ========== 仪表盘 API ==========

@app.route('/api/dashboard')
def api_dashboard():
    """获取仪表盘数据"""
    try:
        status = db_manager.get_status()

        # 获取最近的推荐记录
        recommendations = db_manager.get_recommendations(days=7)

        # 获取特别关注列表
        watchlist = db_manager.get_watchlist()

        # 获取最近的操作记录
        trade_records = db_manager.get_trade_records(days=7)

        return jsonify({
            'success': True,
            'data': {
                'status': status,
                'recent_recommendations': len(recommendations),
                'watchlist_count': len(watchlist),
                'recent_trades': len(trade_records),
                'recommendations': recommendations[:5],  # 只返回最近5条
                'watchlist': [
                    {
                        'stock_code': item.stock_code,
                        'stock_name': item.stock_name,
                        'group_name': item.group_name,
                        'add_date': item.add_date.isoformat()
                    }
                    for item in watchlist[:5]  # 只返回最近5条
                ]
            }
        })
    except Exception as e:
        logger.error(f"获取仪表盘数据失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


# ========== 晨报 API ==========

@app.route('/api/morning/run', methods=['POST'])
def api_morning_run():
    """运行晨报"""
    try:
        # 这里应该调用晨报的完整流程
        # 简化处理，只返回成功
        return jsonify({
            'success': True,
            'message': '晨报运行成功（功能开发中）'
        })
    except Exception as e:
        logger.error(f"运行晨报失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/morning/dry-run', methods=['POST'])
def api_morning_dry_run():
    """预览晨报（不推送）"""
    try:
        # 这里应该调用晨报的预览流程
        # 简化处理，只返回成功
        return jsonify({
            'success': True,
            'message': '晨报预览成功（功能开发中）'
        })
    except Exception as e:
        logger.error(f"预览晨报失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


# ========== 异动监控 API ==========

@app.route('/api/anomaly/run', methods=['POST'])
def api_anomaly_run():
    """运行异动监控"""
    try:
        monitor_config = {
            'push_threshold': config.anomaly_monitor.push_threshold if hasattr(config, 'anomaly_monitor') else 60
        }
        monitor = AnomalyMonitor(monitor_config)
        result = monitor.run()

        return jsonify({
            'success': True,
            'data': {
                'total_score': result.total_score,
                'should_push': result.should_push,
                'scores': [
                    {
                        'dimension': score.dimension,
                        'score': score.score,
                        'description': score.description
                    }
                    for score in result.scores
                ],
                'timestamp': result.timestamp.isoformat()
            }
        })
    except Exception as e:
        logger.error(f"运行异动监控失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


# ========== 晚间回溯 API ==========

@app.route('/api/track/run', methods=['POST'])
def api_track_run():
    """运行晚间回溯"""
    try:
        days = request.json.get('days', 5)

        tracker_config = {
            'tracking_days': config.stock_tracker.tracking_days if hasattr(config, 'stock_tracker') else 5
        }
        tracker = StockTracker(db_manager, tracker_config)
        results = tracker.track_stocks(days)
        report = tracker.generate_report(results)

        return jsonify({
            'success': True,
            'data': {
                'report': report,
                'stocks_count': len(results),
                'tracking_days': days
            }
        })
    except Exception as e:
        logger.error(f"运行晚间回溯失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


# ========== 特别关注 API ==========

@app.route('/api/watchlist')
def api_watchlist():
    """获取特别关注列表"""
    try:
        group = request.args.get('group')
        watchlist = db_manager.get_watchlist(group)

        return jsonify({
            'success': True,
            'data': [
                {
                    'stock_code': item.stock_code,
                    'stock_name': item.stock_name,
                    'add_date': item.add_date.isoformat(),
                    'add_price': item.add_price,
                    'reason': item.reason,
                    'group_name': item.group_name,
                    'tracking_days': item.tracking_days,
                    'is_active': item.is_active
                }
                for item in watchlist
            ]
        })
    except Exception as e:
        logger.error(f"获取特别关注列表失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/watchlist/add', methods=['POST'])
def api_watchlist_add():
    """添加特别关注"""
    try:
        data = request.json
        stock_code = data.get('stock_code')
        stock_name = data.get('stock_name')
        price = data.get('price', 0.0)
        reason = data.get('reason', '')
        group_name = data.get('group_name', '默认')

        if not stock_code or not stock_name:
            return jsonify({'success': False, 'error': '股票代码和名称不能为空'})

        manager = WatchlistManager(db_manager)
        success = manager.add(stock_code, stock_name, price, reason, group_name)

        if success:
            return jsonify({'success': True, 'message': f'添加关注成功: {stock_code} {stock_name}'})
        else:
            return jsonify({'success': False, 'error': '添加关注失败'})
    except Exception as e:
        logger.error(f"添加特别关注失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/watchlist/remove', methods=['POST'])
def api_watchlist_remove():
    """移除特别关注"""
    try:
        data = request.json
        stock_code = data.get('stock_code')

        if not stock_code:
            return jsonify({'success': False, 'error': '股票代码不能为空'})

        manager = WatchlistManager(db_manager)
        success = manager.remove(stock_code)

        if success:
            return jsonify({'success': True, 'message': f'移除关注成功: {stock_code}'})
        else:
            return jsonify({'success': False, 'error': '移除关注失败'})
    except Exception as e:
        logger.error(f"移除特别关注失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/watchlist/groups')
def api_watchlist_groups():
    """获取所有分组"""
    try:
        manager = WatchlistManager(db_manager)
        groups = manager.get_groups()

        return jsonify({
            'success': True,
            'data': groups
        })
    except Exception as e:
        logger.error(f"获取分组列表失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


# ========== 操作日志 API ==========

@app.route('/api/trade/records')
def api_trade_records():
    """获取操作记录"""
    try:
        days = request.args.get('days', 30, type=int)
        journal = TradeJournal(db_manager)
        records = journal.get_records(days)

        return jsonify({
            'success': True,
            'data': [
                {
                    'id': i,
                    'trade_date': record.trade_date.isoformat(),
                    'trade_type': record.trade_type,
                    'stock_code': record.stock_code,
                    'stock_name': record.stock_name,
                    'price': record.price,
                    'quantity': record.quantity,
                    'reason': record.reason,
                    'emotion': record.emotion,
                    'tags': record.tags,
                    'profit_loss': record.profit_loss,
                    'notes': record.notes
                }
                for i, record in enumerate(records)
            ]
        })
    except Exception as e:
        logger.error(f"获取操作记录失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/trade/buy', methods=['POST'])
def api_trade_buy():
    """记录买入"""
    try:
        data = request.json
        stock_code = data.get('stock_code')
        stock_name = data.get('stock_name', '')
        price = data.get('price')
        quantity = data.get('quantity')
        reason = data.get('reason', '')
        emotion = data.get('emotion', '')
        tags = data.get('tags', [])

        if not stock_code or not price or not quantity:
            return jsonify({'success': False, 'error': '股票代码、价格和数量不能为空'})

        journal = TradeJournal(db_manager)
        success = journal.record_buy(stock_code, stock_name, float(price), int(quantity), reason, emotion, tags)

        if success:
            return jsonify({'success': True, 'message': f'记录买入成功: {stock_code} @ {price} x {quantity}'})
        else:
            return jsonify({'success': False, 'error': '记录买入失败'})
    except Exception as e:
        logger.error(f"记录买入失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/trade/sell', methods=['POST'])
def api_trade_sell():
    """记录卖出"""
    try:
        data = request.json
        stock_code = data.get('stock_code')
        stock_name = data.get('stock_name', '')
        price = data.get('price')
        quantity = data.get('quantity')
        reason = data.get('reason', '')
        emotion = data.get('emotion', '')
        tags = data.get('tags', [])
        profit_loss = data.get('profit_loss', 0.0)

        if not stock_code or not price or not quantity:
            return jsonify({'success': False, 'error': '股票代码、价格和数量不能为空'})

        journal = TradeJournal(db_manager)
        success = journal.record_sell(stock_code, stock_name, float(price), int(quantity), reason, emotion, tags, float(profit_loss))

        if success:
            return jsonify({'success': True, 'message': f'记录卖出成功: {stock_code} @ {price} x {quantity}'})
        else:
            return jsonify({'success': False, 'error': '记录卖出失败'})
    except Exception as e:
        logger.error(f"记录卖出失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/trade/stats')
def api_trade_stats():
    """获取交易统计"""
    try:
        days = request.args.get('days', 30, type=int)
        journal = TradeJournal(db_manager)
        stats = journal.calculate_stats(days)
        emotion_stats = journal.calculate_emotion_stats(days)
        tag_stats = journal.calculate_tag_stats(days)

        return jsonify({
            'success': True,
            'data': {
                'stats': {
                    'total_trades': stats.total_trades,
                    'win_count': stats.win_count,
                    'loss_count': stats.loss_count,
                    'win_rate': stats.win_rate,
                    'avg_profit': stats.avg_profit,
                    'avg_loss': stats.avg_loss,
                    'profit_loss_ratio': stats.profit_loss_ratio,
                    'max_profit': stats.max_profit,
                    'max_loss': stats.max_loss
                },
                'emotion_stats': [
                    {
                        'emotion': stat.emotion,
                        'count': stat.count,
                        'win_count': stat.win_count,
                        'win_rate': stat.win_rate
                    }
                    for stat in emotion_stats
                ],
                'tag_stats': [
                    {
                        'tag': stat.tag,
                        'count': stat.count,
                        'win_count': stat.win_count,
                        'win_rate': stat.win_rate
                    }
                    for stat in tag_stats
                ]
            }
        })
    except Exception as e:
        logger.error(f"获取交易统计失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/trade/review')
def api_trade_review():
    """获取复盘报告"""
    try:
        days = request.args.get('days', 30, type=int)
        journal = TradeJournal(db_manager)
        report = journal.generate_review_report(days)

        return jsonify({
            'success': True,
            'data': {
                'report': report
            }
        })
    except Exception as e:
        logger.error(f"获取复盘报告失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


# ========== 数据库管理 API ==========

@app.route('/api/db/status')
def api_db_status():
    """获取数据库状态"""
    try:
        status = db_manager.get_status()

        return jsonify({
            'success': True,
            'data': status
        })
    except Exception as e:
        logger.error(f"获取数据库状态失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/db/backup', methods=['POST'])
def api_db_backup():
    """备份数据库"""
    try:
        backup_dir = request.json.get('backup_dir', 'data/backup')
        db_manager.backup(backup_dir)

        return jsonify({
            'success': True,
            'message': f'数据库备份成功: {backup_dir}'
        })
    except Exception as e:
        logger.error(f"备份数据库失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/db/cleanup', methods=['POST'])
def api_db_cleanup():
    """清理旧数据"""
    try:
        keep_days = request.json.get('keep_days', 30)
        db_manager.cleanup(keep_days)

        return jsonify({
            'success': True,
            'message': f'旧数据清理成功，保留最近{keep_days}天'
        })
    except Exception as e:
        logger.error(f"清理旧数据失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


# ========== 启动函数 ==========

def run_web_server(host='0.0.0.0', port=5000, debug=False):
    """启动 Web 服务器"""
    init_app()

    print(f"Web UI 启动中...")
    print(f"   访问地址: http://localhost:{port}")
    print(f"   按 Ctrl+C 停止服务器")

    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run_web_server(debug=True)
