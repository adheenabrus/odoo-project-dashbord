odoo.define('project_dashboard.Dashboard', function (require) {
    "use strict";

    var core = require('web.core');
    var QWeb = core.qweb;
    var ajax = require('web.ajax');
    var rpc = require('web.rpc');
    var _t = core._t;
    var AbstractAction = require('web.AbstractAction');

    var ProjectDashboard = AbstractAction.extend({
        template: 'ProjectDashboard',
        events: {
            'click .refresh-dashboard': '_onRefreshDashboard',
            'click .total-projects-card': '_onTotalProjectsClick',
            'change #start_date': '_onDateChange',
            'change #end_date': '_onDateChange'
        },

        init: function(parent, context) {
            this._super(parent, context);
            this.dashboardData = {};
            this.charts = {};

            // Set default dates
            var today = new Date();
            var thirtyDaysAgo = new Date();
            thirtyDaysAgo.setDate(today.getDate() - 30);

            this.startDate = this._formatDate(thirtyDaysAgo);
            this.endDate = this._formatDate(today);
        },

        willStart: function() {
            return $.when(
                this._super.apply(this, arguments),
                this._loadDashboardData()
            );
        },

        start: function() {
            return this._super().then(() => {
                // Set initial date values
                this.$('#start_date').val(this.startDate);
                this.$('#end_date').val(this.endDate);
                this._renderCharts();
            });
        },

        _formatDate: function(date) {
            return date.toISOString().split('T')[0];
        },

        _onDateChange: function(ev) {
            // Update start or end date
            var startInput = this.$('#start_date');
            var endInput = this.$('#end_date');

            this.startDate = startInput.val();
            this.endDate = endInput.val();

            // Reload dashboard data
            this._loadDashboardData().then(() => {
                this._renderCharts();
            });
        },

        _loadDashboardData: function() {
            return this._rpc({
                route: '/project/dashboard/data',
                params: {
                    start_date: this.startDate,
                    end_date: this.endDate
                }
            }).then(data => {
                this.dashboardData = data;
            });
        },


         _onTotalProjectsClick: function(ev) {
            ev.preventDefault();
            this.do_action({
                type: 'ir.actions.act_window',
                name: _t('Projects'),
                res_model: 'project.project',
                views: [[false, 'kanban']],
                view_mode: 'kanban',
                target: 'main',
                view_type: 'kanban',
                view_id: 'project.view_project_kanban'
            });
        },

        _renderCharts: function() {
            this._renderWeeklyUtilization();
            this._renderTaskDistribution();
            this._renderBugResolution();
            this._renderCapacityAllocation();
            this._renderTaskCompletion();
            this._renderProjectProgress();
            this._renderTimesheetCompliance();
            this._renderTaskOverruns();
            this._renderWeeklyBurnRate();
            this._renderTaskBacklog();
        },


        _renderWeeklyUtilization: function() {
            const ctx = this.el.querySelector('#weeklyUtilizationChart');

            if (ctx && this.dashboardData.weekly_developer_utilization) {
                if (this.charts.weeklyUtilization) {
                    this.charts.weeklyUtilization.destroy();
                }

                this.charts.weeklyUtilization = new Chart(ctx, {
                    type: 'bar',
                    data: this.dashboardData.weekly_developer_utilization,
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'top',
                                align: 'center',
                                labels: {
                                    padding: 20,  // Add padding between legend items
                                    usePointStyle: true,  // Use point style for legend items
                                    pointStyle: 'rect',   // Use rectangle style for points
                                    boxWidth: 15,         // Set width of legend color box
                                    boxHeight: 15,        // Set height of legend color box
                                    font: {
                                        size: 12         // Set font size for legend labels
                                    }
                                }
                            },

                        },
                        scales: {
                            x: {
                                grid: {
                                    display: false
                                },
                                title: {
                                    display: true,
                                    text: 'Employee Names'
                                }
                            },
                            y: {
                                beginAtZero: true,
                                grid: {
                                    borderDash: [2, 4]
                                },
                                title: {
                                    display: true,
                                    text: 'Hours / Utilization (%)'
                                }
                            }
                        },
                        barPercentage: 0.7,
                        categoryPercentage: 0.8,
                        layout: {
                            padding: {
                                top: 10,     // Add top padding
                                right: 30,   // Reduced right padding since legend is now on top
                                bottom: 10,
                                left: 10
                            }
                        }
                    }
                });
            }
        },


        _renderTaskDistribution: function() {
            const ctx = this.el.querySelector('#taskDistributionChart');
            if (!ctx || !this.dashboardData.task_distribution) {
                return;  // Exit if no context or data
            }

            // Destroy existing chart if it exists
            if (this.charts.taskDistribution) {
                this.charts.taskDistribution.destroy();
            }

            const data = this.dashboardData.task_distribution;
            if (!data.length) {
                return;  // Exit if no data
            }

            // Collect all unique categories across all developers
            const allCategories = new Set();
            data.forEach(dev => {
                dev.categories.forEach(cat => {
                    allCategories.add(cat.type);
                });
            });
            const categories = Array.from(allCategories);

            // Calculate total hours for each category
            const categoryHours = {};
            categories.forEach(cat => {
                categoryHours[cat] = 0;
                data.forEach(dev => {
                    const category = dev.categories.find(c => c.type === cat);
                    if (category) {
                        categoryHours[cat] += category.hours;
                    }
                });
            });

            // Prepare chart data
            const chartData = {
                labels: categories,
                datasets: [{
                    data: categories.map(cat => categoryHours[cat]),
                    backgroundColor: categories.map((_, index) => this._getChartColor(index)),
                    borderWidth: 1
                }]
            };

            // Create new chart
            this.charts.taskDistribution = new Chart(ctx, {
                type: 'pie',
                data: chartData,
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                            labels: {
                                padding: 20
                            }
                        },
                        title: {
                            display: true,
                            padding: {
                                top: 10,
                                bottom: 30
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const value = context.raw;
                                    const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                    const percentage = ((value / total) * 100).toFixed(1);
                                    return `${context.label}: ${value.toFixed(1)} hours (${percentage}%)`;
                                }
                            }
                        }
                    }
                }
            });
        },


        _renderBugResolution: function() {
            const ctx = this.el.querySelector('#bugResolutionChart');
            if (ctx && this.dashboardData.bug_resolution) {
                if (this.charts.bugResolution) {
                    this.charts.bugResolution.destroy();
                }
                this.charts.bugResolution = new Chart(ctx, {
                    type: 'line',
                    data: this.dashboardData.bug_resolution,
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { position: 'top' },
                            title: { display: true, text: 'Bug Resolution Time Trend' }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                title: { display: true, text: 'Hours' }
                            }
                        }
                    }
                });
            }
        },

        _renderCapacityAllocation: function() {
            const ctx = this.el.querySelector('#capacityAllocationChart');
            if (ctx && this.dashboardData.capacity_allocation) {
                if (this.charts.capacityAllocation) {
                    this.charts.capacityAllocation.destroy();
                }

                const data = this.dashboardData.capacity_allocation;

                this.charts.capacityAllocation = new Chart(ctx, {
//                    type: 'heatmap',
                    type: 'bar',

                    data: {
                        labels: data.developers,
                        datasets: data.weeks.map((week, i) => ({
                            label: week,
                            data: data.data.map(row => row[i])
                        }))
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { position: 'top' },
                            title: { display: true, text: 'Developer Capacity vs Allocation' }
                        },
                        scales: {
                            y: { title: { display: true, text: 'Developers' } },
                            x: { title: { display: true, text: 'Weeks' } }
                        }
                    }
                });
            }
        },
        _renderTaskCompletion: function() {
            const ctx = this.el.querySelector('#taskCompletionChart');
            if (ctx && this.dashboardData.task_completion) {
                if (this.charts.taskCompletion) {
                    this.charts.taskCompletion.destroy();
                }

                this.charts.taskCompletion = new Chart(ctx, {
                    type: 'bar',
                    data: this.dashboardData.task_completion,
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'top',
                                align: 'center'
                            },

                        },
                        scales: {
                            x: {
                                ticks: {
                                    maxRotation: 45,
                                    minRotation: 45,
                                    autoSkip: false,
                                    font: {
                                        size: 11
                                    }
                                }
                            },
                            y: {
                                beginAtZero: true,
                                title: {
                                    display: true,
                                    text: 'Number of Tasks'
                                }
                            }
                        },
                        layout: {
                            padding: {
                                left: 10,
                                right: 10,
                                top: 0,
                                bottom: 20
                            }
                        }
                    }
                });
            }
        },
        _renderProjectProgress: function() {
            const ctx = this.el.querySelector('#projectProgressChart');
            if (!ctx || !this.dashboardData.project_progress) return;

            if (this.charts.projectProgressChart) {
                this.charts.projectProgressChart.destroy();
            }

            const data = this.dashboardData.project_progress;

            // Calculate the maximum total tasks for scaling
            const maxTotal = Math.max(...data.total_tasks);

            // Normalize the data to percentages of total width
            const normalizedData = {
                labels: data.labels,
                completed: data.completed.map((val, idx) => (val / data.total_tasks[idx]) * 100),
                remaining: data.remaining.map((val, idx) => (val / data.total_tasks[idx]) * 100)
            };

            this.charts.projectProgressChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: normalizedData.labels,
                    datasets: [
                        {
                            label: 'Completed Tasks',
                            data: normalizedData.completed,
                            backgroundColor: '#B3C100',
                            borderWidth: 0,
                            barPercentage: 0.8
                        },
                        {
                            label: 'Remaining Tasks',
                            data: normalizedData.remaining,
                            backgroundColor: '#D32D41',
                            borderWidth: 0,
                            barPercentage: 0.8
                        }
                    ]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            stacked: true,
                            beginAtZero: true,
                            max: 100,
                            ticks: {
                                display: false
                            },
                            grid: {
                                display: false
                            }
                        },
                        y: {
                            stacked: true,
                            grid: {
                                display: false
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: true,
                            position: 'top',
                            labels: {
                                usePointStyle: true,
                                padding: 20
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    const dataIndex = context.dataIndex;
                                    const completed = data.completed[dataIndex];
                                    const total = data.total_tasks[dataIndex];
                                    const percentage = data.percentages[dataIndex];

                                    if (context.dataset.label === 'Completed Tasks') {
                                        return `Completed: ${completed} of ${total} (${percentage}%)`;
                                    } else {
                                        return `Remaining: ${data.remaining[dataIndex]} of ${total}`;
                                    }
                                }
                            }
                        }
                    },
                    animation: {
                        onComplete: function(animation) {
                            const chart = animation.chart;
                            const ctx = chart.ctx;
                            const yAxis = chart.scales.y;
                            const xAxis = chart.scales.x;

                            chart.data.labels.forEach((label, index) => {
                                const completed = data.completed[index];
                                const total = data.total_tasks[index];
                                const percentage = data.percentages[index];

                                // Calculate position for text
                                const meta = chart.getDatasetMeta(1);
                                const rect = meta.data[index];
                                const x = rect.x + rect.width + 10;
                                const y = rect.y;

                                // Draw percentage
                                ctx.fillStyle = '#000000';
                                ctx.font = 'bold 12px Arial';
                                ctx.textAlign = 'left';
                                ctx.fillText(`${percentage}%`, x, y);

                                // Draw task count below percentage
                                ctx.fillStyle = '#666666';
                                ctx.font = '11px Arial';
                                ctx.fillText(`${completed}/${total} tasks`, x, y + 15);
                            });
                        }
                    }
                }
            });
        },


        _renderTaskOverruns: function() {
            const ctx = this.el.querySelector('#taskOverrunChart');
            if (ctx && this.dashboardData.task_overruns) {
                if (this.charts.taskOverrun) {
                    this.charts.taskOverrun.destroy();
                }
                this.charts.taskOverrun = new Chart(ctx, {
                    type: 'bar',
                    data: this.dashboardData.task_overruns.data,
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { position: 'top' },
                            title: { display: true, text: 'Task Overruns by Developer/Project' },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        const label = context.dataset.label || '';
                                        const value = context.raw || 0;
                                        return `${label}: ${value} ${context.dataset.label === 'Overrun Percentage' ? '%' : ''}`;
                                    }
                                }
                            }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                title: {
                                    display: true,
                                    text: 'Count / Percentage'
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: 'Developer / Project'
                                }
                            }
                        }
                    }
                });
            }
        },
//
        _renderTimesheetCompliance: function() {
            const ctx = this.el.querySelector('#timesheetComplianceChart');
            if (ctx && this.dashboardData.timesheet_compliance) {
                if (this.charts.timesheetCompliance) {
                    this.charts.timesheetCompliance.destroy();
                }
                this.charts.timesheetCompliance = new Chart(ctx, {
                    type: 'doughnut',  // Change to 'doughnut' for the donut style
                    data: this.dashboardData.timesheet_compliance,
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { position: 'right' },
                            title: { display: true, text: 'Timesheet Compliance' },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        const label = context.label || '';
                                        const value = context.raw || 0;
                                        return `${label}: ${value}%`;
                                    }
                                }
                            }
                        }
                    }
                });
            }
        },
        _renderWeeklyBurnRate: function() {
            const ctx = this.el.querySelector('#weeklyBurnRateChart');
            if (ctx && this.dashboardData.weekly_burn_rate) {
                if (this.charts.weeklyBurnRate) {
                    this.charts.weeklyBurnRate.destroy();
                }
                this.charts.weeklyBurnRate = new Chart(ctx, {
                    type: 'line',
                    data: this.dashboardData.weekly_burn_rate,
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { position: 'top' },
                            title: { display: true, text: 'Weekly Burn Rate' }
                        },
                        scales: {
                            y: { beginAtZero: true }
                        }
                    }
                });
            }
        },

        _renderTaskBacklog: function() {
            const ctx = this.el.querySelector('#taskBacklogChart');
            if (ctx && this.dashboardData.task_backlog) {
                if (this.charts.taskBacklog) {
                    this.charts.taskBacklog.destroy();
                }
                this.charts.taskBacklog = new Chart(ctx, {
                    type: 'bar',
                    data: this.dashboardData.task_backlog,
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { position: 'top' },
                            title: { display: true, text: 'Task Backlog' }
                        },
                        scales: {
                            y: { beginAtZero: true }
                        }
                    }
                });
            }
        },


        _getChartColor: function(index) {
            const colors = [
                '#B3C100',  // Lime Green
                '#CED2CC',  // Light Gray
                '#23282D',  // Dark Gray
                '#4CB5F5',  // Sky Blue
                '#1F3F49',  // Dark Blue
                '#D32D41',  // Red
                '#6AB187'   // Sage Green
            ];
            return colors[index % colors.length];
        },

        _onRefreshDashboard: function() {
            this._loadDashboardData().then(() => {
                this._renderCharts();
            });
        }
    });

    core.action_registry.add('project_dashboard', ProjectDashboard);
    return ProjectDashboard;
});





























//
//old code before total project error""

//odoo.define('Dashboard', function(require) {
//    "use strict";
//
//    var AbstractAction = require('web.AbstractAction');

//
//    var ProjectDashboard = AbstractAction.extend({
//        template: 'ProjectDashboard',
//
//        init: function(parent, context) {
//            this._super(parent, context);
//            this.charts = {};
//            this.dashboardData = {};
//        },
//
//        willStart: function() {
//            var self = this;
//            return $.when(
//                this._super.apply(this, arguments),
//                this._loadDashboardData()
//            );
//        },
//
//        start: function() {
//            var self = this;
//            return this._super().then(function() {
//                self._renderCharts();
//            });
//        },
//
//        _loadDashboardData: function() {
//            var self = this;
//            return $.when(
//                self._rpc({
//                    model: 'project.task',
//                    method: 'get_developer_utilization_data',
//                    args: [],
//                }),
//                self._rpc({
//                    model: 'project.task',
//                    method: 'get_task_completion_data',
//                    args: [],
//                }),
//                self._rpc({
//                    model: 'project.task',
//                    method: 'get_project_progress_data',
//                    args: [],
//                }),
//                self._rpc({
//                    model: 'project.task',
//                    method: 'get_timesheet_compliance_data',
//                    args: [],
//                })
//            ).then(function(developerData, taskData, progressData, timesheetData) {
//                self.dashboardData = {
//                    developer_utilization: developerData,
//                    task_completion: taskData,
//                    project_progress: progressData,
//                    timesheet_compliance: timesheetData
//                };
//            });
//        },
//
//        _renderCharts: function() {
//            var self = this;
//
//            // Developer Utilization Chart
//            var devCtx = self.el.querySelector('#developerUtilizationChart');
//            if (devCtx && self.dashboardData.developer_utilization) {
//                if (self.charts.developerUtilization) {
//                    self.charts.developerUtilization.destroy();
//                }
//                self.charts.developerUtilization = new Chart(devCtx, {
//                    type: 'bar',
//type: 'bar',
//                    data: self.dashboardData.developer_utilization,
//     data: self.dashboardData.developer_utilization,
//                    options: {
//                        responsive: true,
//                        maintainAspectRatio: false,
//                        plugins: {
//                            legend: { position: 'top' }
//                        },
//                        scales: {
//                            y: {
//                                beginAtZero: true,
//                                max: 100,
//                                title: {
//                                    display: true,
//                                    text: 'Utilization %'
//                                }
//                            }
//                        }
//                    }
//                });
//            }
//
//            // Task Completion Chart
//            var taskCtx = self.el.querySelector('#taskCompletionChart');
//            if (taskCtx && self.dashboardData.task_completion) {
//                if (self.charts.taskCompletion) {
//                    self.charts.taskCompletion.destroy();
//                }
//                self.charts.taskCompletion = new Chart(taskCtx, {
//                    type: 'line',
//                    data: self.dashboardData.task_completion,
//                    options: {
//                        responsive: true,
//                        maintainAspectRatio: false,
//                        plugins: {
//                            legend: { position: 'top' }
//                        }
//                    }
//                });
//            }
//
//            // Project Progress Chart
//            var progressCtx = self.el.querySelector('#projectProgressChart');
//            if (progressCtx && self.dashboardData.project_progress) {
//                if (self.charts.projectProgress) {
//                    self.charts.projectProgress.destroy();
//                }
//                self.charts.projectProgress = new Chart(progressCtx, {
//                    type: 'bar',
//                    data: self.dashboardData.project_progress,
//                    options: {
//                        responsive: true,
//                        maintainAspectRatio: false,
//                        plugins: {
//                            legend: { position: 'top' }
//                        },
//                        scales: {
//                            y: {
//                                beginAtZero: true,
//                                max: 100,
//                                title: {
//                                    display: true,
//                                    text: 'Progress %'
//                                }
//                            }
//                        }
//                    }
//                });
//            }
//
//            // Timesheet Compliance Chart
//            var timesheetCtx = self.el.querySelector('#timesheetComplianceChart');
//            if (timesheetCtx && self.dashboardData.timesheet_compliance) {
//                if (self.charts.timesheetCompliance) {
//                    self.charts.timesheetCompliance.destroy();
//                }
//                self.charts.timesheetCompliance = new Chart(timesheetCtx, {
//                    type: 'doughnut',
//                    data: self.dashboardData.timesheet_compliance,
//                    options: {
//                        responsive: true,
//                        maintainAspectRatio: false,
//                        plugins: {
//                            legend: { position: 'right' }
//                        }
//                    }
//                });
//            }
//        },
//
//        destroy: function() {
//            Object.values(this.charts).forEach(chart => {
//                if (chart) {
//                    chart.destroy();
//                }
//            });
//            this._super.apply(this, arguments);
//        }
//    });
//
//    core.action_registry.add('project_dashboard', ProjectDashboard);
//    return ProjectDashboard;
//});