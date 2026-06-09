// 全局变量
let currentPage = 'dashboard';

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    // 初始化导航菜单
    initNavigation();

    // 加载仪表盘数据
    loadDashboard();
});

// 初始化导航菜单
function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item');

    navItems.forEach(item => {
        item.addEventListener('click', function() {
            const page = this.dataset.page;

            // 更新导航状态
            navItems.forEach(nav => nav.classList.remove('active'));
            this.classList.add('active');

            // 切换页面
            switchPage(page);
        });
    });
}

// 切换页面
function switchPage(page) {
    // 隐藏所有页面
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));

    // 显示目标页面
    const targetPage = document.getElementById(`page-${page}`);
    if (targetPage) {
        targetPage.classList.add('active');
        currentPage = page;

        // 加载页面数据
        loadPageData(page);
    }
}

// 加载页面数据
function loadPageData(page) {
    switch(page) {
        case 'dashboard':
            loadDashboard();
            break;
        case 'watchlist':
            loadWatchlist();
            break;
        case 'trade':
            loadTradeStats();
            loadTradeRecords();
            break;
        case 'database':
            loadDbStatus();
            break;
    }
}

// 显示 Toast 消息
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    const toastMessage = document.getElementById('toast-message');

    toast.className = 'toast ' + type;
    toastMessage.textContent = message;
    toast.style.display = 'block';

    setTimeout(() => {
        toast.style.display = 'none';
    }, 3000);
}

// API 请求封装
async function apiRequest(url, method = 'GET', data = null) {
    try {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json'
            }
        };

        if (data && method !== 'GET') {
            options.body = JSON.stringify(data);
        }

        const response = await fetch(url, options);
        const result = await response.json();

        if (!result.success) {
            throw new Error(result.error || '请求失败');
        }

        return result.data;
    } catch (error) {
        console.error('API 请求失败:', error);
        showToast(error.message, 'error');
        throw error;
    }
}

// ========== 仪表盘功能 ==========

async function loadDashboard() {
    try {
        const data = await apiRequest('/api/dashboard');

        // 更新统计卡片
        document.getElementById('stat-daily-db').textContent = data.status.daily_db_count;
        document.getElementById('stat-watchlist').textContent = data.watchlist_count;
        document.getElementById('stat-trades').textContent = data.recent_trades;
        document.getElementById('stat-recommendations').textContent = data.recent_recommendations;

        // 更新最近推荐列表
        const recommendationsContainer = document.getElementById('recent-recommendations');
        if (data.recommendations && data.recommendations.length > 0) {
            recommendationsContainer.innerHTML = data.recommendations.map(rec => `
                <div class="list-item">
                    <h4>${rec.stock_code} ${rec.stock_name}</h4>
                    <p>推荐价格: ${rec.recommend_price}</p>
                    <div class="meta">
                        <span>来源: ${rec.source}</span>
                        <span>日期: ${rec.recommend_date}</span>
                    </div>
                </div>
            `).join('');
        } else {
            recommendationsContainer.innerHTML = '<p class="empty-message">暂无推荐记录</p>';
        }

        // 更新特别关注列表
        const watchlistContainer = document.getElementById('recent-watchlist');
        if (data.watchlist && data.watchlist.length > 0) {
            watchlistContainer.innerHTML = data.watchlist.map(item => `
                <div class="list-item">
                    <h4>${item.stock_code} ${item.stock_name}</h4>
                    <p>分组: ${item.group_name}</p>
                    <div class="meta">
                        <span>关注日期: ${item.add_date}</span>
                    </div>
                </div>
            `).join('');
        } else {
            watchlistContainer.innerHTML = '<p class="empty-message">暂无特别关注</p>';
        }
    } catch (error) {
        console.error('加载仪表盘数据失败:', error);
    }
}

// ========== 晨报功能 ==========

async function runMorning() {
    try {
        await apiRequest('/api/morning/run', 'POST');
        showToast('晨报运行成功', 'success');
    } catch (error) {
        showToast('晨报运行失败: ' + error.message, 'error');
    }
}

async function runMorningDryRun() {
    try {
        await apiRequest('/api/morning/dry-run', 'POST');
        showToast('晨报预览成功', 'success');
    } catch (error) {
        showToast('晨报预览失败: ' + error.message, 'error');
    }
}

// ========== 异动监控功能 ==========

async function runAnomaly() {
    try {
        const data = await apiRequest('/api/anomaly/run', 'POST');

        // 显示结果
        const resultContainer = document.getElementById('anomaly-result');
        resultContainer.style.display = 'block';

        // 显示各维度分数
        const scoresGrid = document.getElementById('anomaly-scores');
        scoresGrid.innerHTML = data.scores.map(score => `
            <div class="score-card">
                <h4>${score.dimension}</h4>
                <div class="score">${score.score.toFixed(1)}/25</div>
                <div class="description">${score.description}</div>
            </div>
        `).join('');

        // 显示摘要
        const summaryBox = document.getElementById('anomaly-summary');
        summaryBox.innerHTML = `
            <h4>监控结果</h4>
            <p>总分: <strong>${data.total_score.toFixed(1)}/100</strong></p>
            <p>推送阈值: 60</p>
            <p>是否推送: <strong>${data.should_push ? '是' : '否'}</strong></p>
            <p>监控时间: ${data.timestamp}</p>
        `;

        showToast('异动监控完成', 'success');
    } catch (error) {
        showToast('异动监控失败: ' + error.message, 'error');
    }
}

// ========== 晚间回溯功能 ==========

async function runTrack() {
    try {
        const days = parseInt(document.getElementById('track-days').value) || 5;
        const data = await apiRequest('/api/track/run', 'POST', { days });

        // 显示结果
        const resultContainer = document.getElementById('track-result');
        resultContainer.style.display = 'block';

        const output = document.getElementById('track-output');
        output.textContent = data.report;

        showToast('晚间回溯完成', 'success');
    } catch (error) {
        showToast('晚间回溯失败: ' + error.message, 'error');
    }
}

// ========== 特别关注功能 ==========

async function loadWatchlist() {
    try {
        const data = await apiRequest('/api/watchlist');

        const container = document.getElementById('watchlist-container');
        if (data && data.length > 0) {
            container.innerHTML = `
                <table>
                    <thead>
                        <tr>
                            <th>股票代码</th>
                            <th>股票名称</th>
                            <th>分组</th>
                            <th>关注价格</th>
                            <th>关注理由</th>
                            <th>关注日期</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.map(item => `
                            <tr>
                                <td>${item.stock_code}</td>
                                <td>${item.stock_name}</td>
                                <td>${item.group_name}</td>
                                <td>${item.add_price || '-'}</td>
                                <td>${item.reason || '-'}</td>
                                <td>${item.add_date}</td>
                                <td>
                                    <button class="btn btn-danger btn-sm" onclick="removeWatchlist('${item.stock_code}')">
                                        <i class="fas fa-trash"></i> 删除
                                    </button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        } else {
            container.innerHTML = '<p class="empty-message">暂无特别关注</p>';
        }
    } catch (error) {
        console.error('加载特别关注列表失败:', error);
    }
}

async function addWatchlist() {
    try {
        const stockCode = document.getElementById('watch-stock-code').value;
        const stockName = document.getElementById('watch-stock-name').value;
        const price = parseFloat(document.getElementById('watch-price').value) || 0;
        const group = document.getElementById('watch-group').value;
        const reason = document.getElementById('watch-reason').value;

        if (!stockCode || !stockName) {
            showToast('股票代码和名称不能为空', 'error');
            return;
        }

        await apiRequest('/api/watchlist/add', 'POST', {
            stock_code: stockCode,
            stock_name: stockName,
            price: price,
            group_name: group,
            reason: reason
        });

        showToast('添加关注成功', 'success');

        // 清空表单
        document.getElementById('watch-stock-code').value = '';
        document.getElementById('watch-stock-name').value = '';
        document.getElementById('watch-price').value = '';
        document.getElementById('watch-reason').value = '';

        // 重新加载列表
        loadWatchlist();
    } catch (error) {
        showToast('添加关注失败: ' + error.message, 'error');
    }
}

async function removeWatchlist(stockCode) {
    try {
        if (!confirm(`确定要删除 ${stockCode} 的关注吗？`)) {
            return;
        }

        await apiRequest('/api/watchlist/remove', 'POST', {
            stock_code: stockCode
        });

        showToast('移除关注成功', 'success');

        // 重新加载列表
        loadWatchlist();
    } catch (error) {
        showToast('移除关注失败: ' + error.message, 'error');
    }
}

// ========== 操作日志功能 ==========

// 初始化标签页
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        const tab = this.dataset.tab;

        // 更新标签页状态
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        this.classList.add('active');

        // 切换内容
        document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
        document.getElementById(`tab-${tab}`).classList.add('active');
    });
});

async function recordBuy() {
    try {
        const stockCode = document.getElementById('buy-stock-code').value;
        const stockName = document.getElementById('buy-stock-name').value;
        const price = parseFloat(document.getElementById('buy-price').value);
        const quantity = parseInt(document.getElementById('buy-quantity').value);
        const reason = document.getElementById('buy-reason').value;
        const emotion = document.getElementById('buy-emotion').value;
        const tagsSelect = document.getElementById('buy-tags');
        const tags = Array.from(tagsSelect.selectedOptions).map(option => option.value);

        if (!stockCode || !price || !quantity) {
            showToast('股票代码、价格和数量不能为空', 'error');
            return;
        }

        await apiRequest('/api/trade/buy', 'POST', {
            stock_code: stockCode,
            stock_name: stockName,
            price: price,
            quantity: quantity,
            reason: reason,
            emotion: emotion,
            tags: tags
        });

        showToast('记录买入成功', 'success');

        // 清空表单
        document.getElementById('buy-stock-code').value = '';
        document.getElementById('buy-stock-name').value = '';
        document.getElementById('buy-price').value = '';
        document.getElementById('buy-quantity').value = '';
        document.getElementById('buy-reason').value = '';
        document.getElementById('buy-emotion').value = '';
        tagsSelect.selectedIndex = -1;

        // 重新加载数据
        loadTradeStats();
        loadTradeRecords();
    } catch (error) {
        showToast('记录买入失败: ' + error.message, 'error');
    }
}

async function recordSell() {
    try {
        const stockCode = document.getElementById('sell-stock-code').value;
        const stockName = document.getElementById('sell-stock-name').value;
        const price = parseFloat(document.getElementById('sell-price').value);
        const quantity = parseInt(document.getElementById('sell-quantity').value);
        const reason = document.getElementById('sell-reason').value;
        const emotion = document.getElementById('sell-emotion').value;
        const profitLoss = parseFloat(document.getElementById('sell-profit-loss').value) || 0;

        if (!stockCode || !price || !quantity) {
            showToast('股票代码、价格和数量不能为空', 'error');
            return;
        }

        await apiRequest('/api/trade/sell', 'POST', {
            stock_code: stockCode,
            stock_name: stockName,
            price: price,
            quantity: quantity,
            reason: reason,
            emotion: emotion,
            profit_loss: profitLoss
        });

        showToast('记录卖出成功', 'success');

        // 清空表单
        document.getElementById('sell-stock-code').value = '';
        document.getElementById('sell-stock-name').value = '';
        document.getElementById('sell-price').value = '';
        document.getElementById('sell-quantity').value = '';
        document.getElementById('sell-reason').value = '';
        document.getElementById('sell-emotion').value = '';
        document.getElementById('sell-profit-loss').value = '';

        // 重新加载数据
        loadTradeStats();
        loadTradeRecords();
    } catch (error) {
        showToast('记录卖出失败: ' + error.message, 'error');
    }
}

async function loadTradeStats() {
    try {
        const days = parseInt(document.getElementById('stats-days').value) || 30;
        const data = await apiRequest(`/api/trade/stats?days=${days}`);

        const container = document.getElementById('trade-stats');

        if (data.stats.total_trades > 0) {
            container.innerHTML = `
                <div class="stat-card">
                    <div class="stat-icon"><i class="fas fa-chart-bar"></i></div>
                    <div class="stat-info">
                        <h3>${data.stats.total_trades}</h3>
                        <p>总交易次数</p>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon" style="background-color: var(--success-color)"><i class="fas fa-check"></i></div>
                    <div class="stat-info">
                        <h3>${(data.stats.win_rate * 100).toFixed(1)}%</h3>
                        <p>胜率</p>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon" style="background-color: var(--warning-color)"><i class="fas fa-balance-scale"></i></div>
                    <div class="stat-info">
                        <h3>${data.stats.profit_loss_ratio.toFixed(2)}</h3>
                        <p>盈亏比</p>
                    </div>
                </div>
                <div class="stat-card">
                    <div class="stat-icon" style="background-color: var(--danger-color)"><i class="fas fa-arrow-down"></i></div>
                    <div class="stat-info">
                        <h3>${(data.stats.max_loss * 100).toFixed(2)}%</h3>
                        <p>最大亏损</p>
                    </div>
                </div>
            `;
        } else {
            container.innerHTML = '<p class="empty-message">暂无统计数据</p>';
        }
    } catch (error) {
        console.error('加载交易统计失败:', error);
    }
}

async function loadTradeRecords() {
    try {
        const data = await apiRequest('/api/trade/records?days=30');

        const container = document.getElementById('trade-records');

        if (data && data.length > 0) {
            container.innerHTML = `
                <table>
                    <thead>
                        <tr>
                            <th>时间</th>
                            <th>类型</th>
                            <th>股票代码</th>
                            <th>股票名称</th>
                            <th>价格</th>
                            <th>数量</th>
                            <th>理由</th>
                            <th>情绪</th>
                            <th>盈亏</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.map(record => `
                            <tr>
                                <td>${new Date(record.trade_date).toLocaleString()}</td>
                                <td><span class="badge ${record.trade_type === 'BUY' ? 'badge-success' : 'badge-danger'}">${record.trade_type}</span></td>
                                <td>${record.stock_code}</td>
                                <td>${record.stock_name || '-'}</td>
                                <td>${record.price || '-'}</td>
                                <td>${record.quantity || '-'}</td>
                                <td>${record.reason || '-'}</td>
                                <td>${record.emotion || '-'}</td>
                                <td>${record.profit_loss ? (record.profit_loss * 100).toFixed(2) + '%' : '-'}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
        } else {
            container.innerHTML = '<p class="empty-message">暂无操作记录</p>';
        }
    } catch (error) {
        console.error('加载操作记录失败:', error);
    }
}

// ========== 数据库管理功能 ==========

async function loadDbStatus() {
    try {
        const data = await apiRequest('/api/db/status');

        const container = document.getElementById('db-status');
        container.innerHTML = `
            <div class="stat-card">
                <div class="stat-icon"><i class="fas fa-database"></i></div>
                <div class="stat-info">
                    <h3>${data.daily_db_count}</h3>
                    <p>每日数据库</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><i class="fas fa-star"></i></div>
                <div class="stat-info">
                    <h3>${data.watchlist_count}</h3>
                    <p>特别关注</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><i class="fas fa-exchange-alt"></i></div>
                <div class="stat-info">
                    <h3>${data.trade_record_count}</h3>
                    <p>操作记录</p>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon"><i class="fas fa-hdd"></i></div>
                <div class="stat-info">
                    <h3>${(data.global_db_size / 1024).toFixed(2)} KB</h3>
                    <p>数据库大小</p>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('加载数据库状态失败:', error);
    }
}

async function backupDb() {
    try {
        await apiRequest('/api/db/backup', 'POST');
        showToast('数据库备份成功', 'success');
    } catch (error) {
        showToast('数据库备份失败: ' + error.message, 'error');
    }
}

async function cleanupDb() {
    try {
        if (!confirm('确定要清理旧数据吗？这将删除30天前的数据。')) {
            return;
        }

        await apiRequest('/api/db/cleanup', 'POST');
        showToast('旧数据清理成功', 'success');

        // 重新加载状态
        loadDbStatus();
    } catch (error) {
        showToast('旧数据清理失败: ' + error.message, 'error');
    }
}
