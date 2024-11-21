from odoo import models, fields, api
from datetime import datetime, timedelta
from collections import defaultdict

from odoo.odoo.http import request


class ProjectTask(models.Model):
    _inherit = 'project.task'

    task_start_date = fields.Datetime('Start Date')
    task_end_date = fields.Datetime('End Date')
    actual_hours = fields.Float('Actual Hours', compute='_compute_actual_hours', store=True)
    utilization = fields.Float('Utilization %', compute='_compute_utilization', store=True)
    task_type = fields.Selection([
        ('coding', 'Coding'),
        ('bug_fix', 'Bug Fix'),
        ('testing', 'Testing'),
        ('review', 'Review'),
        ('documentation', 'Documentation')
    ], string='Task Type', default='coding')
    is_bug = fields.Boolean('Is Bug')
    bug_reported_date = fields.Datetime('Bug Reported Date')
    bug_resolution_date = fields.Datetime('Bug Resolution Date')
    is_overdue = fields.Boolean('Is Overdue', compute='_compute_is_overdue', store=True)

    @api.depends('timesheet_ids.unit_amount')
    def _compute_actual_hours(self):
        for task in self:
            task.actual_hours = sum(task.timesheet_ids.mapped('unit_amount'))

    @api.depends('planned_hours', 'actual_hours')
    def _compute_utilization(self):
        for task in self:
            task.utilization = (task.actual_hours / task.planned_hours * 100) if task.planned_hours else 0

    @api.depends('date_deadline', 'task_end_date')
    def _compute_is_overdue(self):
        for task in self:
            if task.task_end_date and task.date_deadline:
                task.is_overdue = task.task_end_date > task.date_deadline
            else:
                task.is_overdue = False

    def _get_chart_colors(self, type='primary'):
        """
        Returns color schemes for charts with both primary and solid/transparent options
        """
        colors = {
            'primary': [
                '#B3C100',  # Lime Green
                '#CED2CC',  # Light Gray
                '#23282D',  # Dark Gray
                '#4CB5F5',  # Sky Blue
                '#1F3F49',  # Dark Blue
                '#D32D41',  # Red
                '#6AB187'  # Sage Green
            ],
            'secondary': [
                'rgba(179, 193, 0, 0.7)',  # Lime Green transparent
                'rgba(206, 210, 204, 0.7)',  # Light Gray transparent
                'rgba(35, 40, 45, 0.7)',  # Dark Gray transparent
                'rgba(76, 181, 245, 0.7)',  # Sky Blue transparent
                'rgba(31, 63, 73, 0.7)',  # Dark Blue transparent
                'rgba(211, 45, 65, 0.7)',  # Red transparent
                'rgba(106, 177, 135, 0.7)'  # Sage Green transparent
            ]
        }
        return colors.get(type, colors['primary'])

    def _get_weekly_developer_utilization(self, start_date, end_date):
        employees = self.env['hr.employee'].search([('active', '=', True)])
        colors = self._get_chart_colors()
        secondary_colors = self._get_chart_colors('secondary')

        data = {
            'labels': [],
            'datasets': [
                {
                    'label': 'Utilization (%)',
                    'data': [],
                    'backgroundColor': secondary_colors[0],
                    'borderColor': colors[0],
                    'borderWidth': 1,
                    'type': 'bar'
                },
                {
                    'label': 'Logged Hours',
                    'data': [],
                    'backgroundColor': secondary_colors[1],
                    'borderColor': colors[1],
                    'borderWidth': 1,
                    'type': 'bar'
                },
                {
                    'label': 'Estimated Hours',
                    'data': [],
                    'backgroundColor': secondary_colors[2],
                    'borderColor': colors[2],
                    'borderWidth': 1,
                    'type': 'bar'
                }
            ]
        }

        for employee in employees:
            user = self.env['res.users'].search([('employee_id', '=', employee.id)], limit=1)
            data['labels'].append(employee.name)

            tasks = self.env['project.task'].search([
                ('user_ids', 'in', [user.id]) if user else ('id', '=', False),
                ('task_start_date', '>=', start_date),
                ('task_start_date', '<=', end_date)
            ])

            estimated_hours = sum(tasks.mapped('planned_hours'))

            timesheets = self.env['account.analytic.line'].search([
                ('employee_id', '=', employee.id),
                ('date', '>=', start_date),
                ('date', '<=', end_date)
            ])
            logged_hours = sum(timesheets.mapped('unit_amount'))

            utilization_percentage = (logged_hours / estimated_hours * 100) if estimated_hours else 0

            data['datasets'][0]['data'].append(round(utilization_percentage, 2))
            data['datasets'][1]['data'].append(round(logged_hours, 2))
            data['datasets'][2]['data'].append(round(estimated_hours, 2))

        return data

    def _get_task_distribution(self, start_date=False, end_date=False, _logger=None):
        """
        Get task type distribution breakdown for each developer
        """
        if not start_date:
            start_date = fields.Date.today() - timedelta(days=30)
        if not end_date:
            end_date = fields.Date.today()

        # Ensure we have datetime objects
        if isinstance(start_date, str):
            start_date = fields.Date.from_string(start_date)
        if isinstance(end_date, str):
            end_date = fields.Date.from_string(end_date)

        developers = self.env['res.users'].search([
            ('share', '=', False),
            ('active', '=', True)
        ])

        colors = self._get_chart_colors()
        data = []

        # Get all unique task types first
        all_task_types = self.env['project.task'].search([
            ('create_date', '>=', start_date),
            ('create_date', '<=', end_date)
        ]).mapped('task_type')
        all_task_types = list(set(all_task_types))  # Remove duplicates

        for dev in developers:
            try:
                tasks = self.env['project.task'].search([
                    ('user_ids', 'in', [dev.id]),
                    ('create_date', '>=', start_date),
                    ('create_date', '<=', end_date)
                ])

                if not tasks:
                    continue

                categories = []
                for index, task_type in enumerate(all_task_types):
                    type_tasks = tasks.filtered(lambda t: t.task_type == task_type)
                    hours = sum(type_tasks.mapped('actual_hours') or [0.0])

                    if hours > 0:  # Only add categories with hours
                        categories.append({
                            'type': task_type or 'Undefined',
                            'hours': float(hours),
                            'color': colors[index % len(colors)]
                        })

                if categories:  # Only add developer if they have task hours
                    data.append({
                        'developer': dev.name,
                        'categories': categories
                    })
            except Exception as e:
                _logger.error(f"Error processing developer {dev.name}: {str(e)}")
                continue

        return data

    def _get_bug_resolution_data(self, start_date, end_date, interval):
        end_date = fields.Datetime.now()
        start_date = end_date - timedelta(weeks=12)
        colors = self._get_chart_colors()

        bug_tasks = self.search([
            ('is_bug', '=', True),
            ('bug_resolution_date', '>=', start_date),
            ('bug_resolution_date', '<=', end_date)
        ])

        data = {
            'labels': [end_date - timedelta(weeks=i) for i in range(12)],
            'datasets': [{
                'label': 'Bug Resolution Time',
                'data': [
                    sum(bug_tasks.filtered(
                        lambda t: t.bug_resolution_date >= start_date + timedelta(weeks=i) and
                                t.bug_resolution_date < start_date + timedelta(weeks=i + 1)
                    ).mapped('actual_hours'))
                    for i in range(12)
                ],
                'borderColor': colors[0],
                'backgroundColor': self._get_chart_colors('secondary')[0],
                'tension': 0.1
            }]
        }
        return data


    def _get_task_completion_data(self, start_date=None, end_date=None):
        # Get all developers (users) who are not portal/public users
        developers = self.env['res.users'].search([
            ('share', '=', False),
            ('active', '=', True)
        ])

        colors = self._get_chart_colors()
        secondary_colors = self._get_chart_colors('secondary')

        data = {
            'labels': [],
            'datasets': [
                {
                    'label': 'Completed Early',
                    'data': [],
                    'backgroundColor': secondary_colors[0],
                    'borderColor': colors[0],
                    'borderWidth': 1
                },
                {
                    'label': 'Completed On Time',
                    'data': [],
                    'backgroundColor': secondary_colors[1],
                    'borderColor': colors[1],
                    'borderWidth': 1
                },
                {
                    'label': 'Completed Late',
                    'data': [],
                    'backgroundColor': secondary_colors[2],
                    'borderColor': colors[2],
                    'borderWidth': 1
                }
            ]
        }

        # If no dates provided, use a default range
        if not start_date or not end_date:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)

        # Add all developers to labels first
        for dev in developers:
            data['labels'].append(dev.name)

        # Initialize data arrays with zeros for all developers
        for dataset in data['datasets']:
            dataset['data'] = [0] * len(developers)

        # Now populate the data for developers who have tasks
        for i, dev in enumerate(developers):
            tasks = self.search([
                ('user_ids', 'in', [dev.id]),
                ('stage_id.fold', '=', True),
                ('date_last_stage_update', '>=', start_date),
                ('date_last_stage_update', '<=', end_date)
            ])

            early = 0
            on_time = 0
            late = 0

            for task in tasks:
                if task.date_deadline and task.date_last_stage_update:
                    deadline = fields.Datetime.to_datetime(task.date_deadline)
                    last_update = fields.Datetime.to_datetime(task.date_last_stage_update)

                    if deadline > last_update:
                        early += 1
                    elif deadline == last_update:
                        on_time += 1
                    else:
                        late += 1

            # Update data at the correct index for this developer
            data['datasets'][0]['data'][i] = early
            data['datasets'][1]['data'][i] = on_time
            data['datasets'][2]['data'][i] = late

        return data

    def _get_project_progress_data(self):
        # Get all active projects
        all_projects = self.env['project.project'].search([('active', '=', True)])

        # Get all tasks
        domain = [
            ('project_id', 'in', all_projects.ids),
            ('active', '=', True)
        ]

        all_tasks = self.env['project.task'].search(domain)

        data = {
            'labels': [],
            'completed': [],
            'remaining': [],
            'percentages': [],
            'total_tasks': []
        }

        # Group tasks by project
        tasks_by_project = {}
        for task in all_tasks:
            if task.project_id not in tasks_by_project:
                tasks_by_project[task.project_id] = {
                    'total': 0,
                    'completed': 0
                }
            tasks_by_project[task.project_id]['total'] += 1
            if task.stage_id.fold:  # Check if task is in a folded stage (completed)
                tasks_by_project[task.project_id]['completed'] += 1

        # Prepare data for each project
        for project in all_projects:
            project_stats = tasks_by_project.get(project, {'total': 0, 'completed': 0})
            total_tasks = project_stats['total']

            if total_tasks > 0:
                completed_tasks = project_stats['completed']
                remaining_tasks = total_tasks - completed_tasks
                completion_percentage = round((completed_tasks / total_tasks) * 100)

                data['labels'].append(project.name)
                data['completed'].append(completed_tasks)
                data['remaining'].append(remaining_tasks)
                data['percentages'].append(completion_percentage)
                data['total_tasks'].append(total_tasks)

        return data

    def _get_task_overruns_data(self):
        tasks = self.search([])
        colors = self._get_chart_colors()
        secondary_colors = self._get_chart_colors('secondary')
        overrun_data = {}

        for task in tasks:
            if task.effective_hours > task.planned_hours:
                overrun = task.effective_hours - task.planned_hours
                if task.user_ids:
                    for user in task.user_ids:
                        key = f"{user.name} ({task.project_id.name})"
                        if key not in overrun_data:
                            overrun_data[key] = {'count': 0, 'overrun_hours': 0.0}
                        overrun_data[key]['count'] += 1
                        overrun_data[key]['overrun_hours'] += overrun
                else:
                    key = task.project_id.name
                    if key not in overrun_data:
                        overrun_data[key] = {'count': 0, 'overrun_hours': 0.0}
                    overrun_data[key]['count'] += 1
                    overrun_data[key]['overrun_hours'] += overrun

        total_tasks = sum(data['count'] for data in overrun_data.values())
        total_overrun_hours = sum(data['overrun_hours'] for data in overrun_data.values())

        labels = list(overrun_data.keys())
        overrun_count_data = [data['count'] for data in overrun_data.values()]
        overrun_percentage_data = [
            round((data['count'] / total_tasks) * 100, 1) if total_tasks else 0
            for data in overrun_data.values()
        ]

        data = {
            'labels': labels,
            'datasets': [
                {
                    'label': 'Task Overrun Count',
                    'data': overrun_count_data,
                    'backgroundColor': secondary_colors[0],
                    'borderColor': colors[0],
                    'borderWidth': 1
                },
                {
                    'label': 'Overrun Percentage',
                    'data': overrun_percentage_data,
                    'type': 'line',
                    'backgroundColor': secondary_colors[1],
                    'borderColor': colors[1],
                    'borderWidth': 2
                }
            ]
        }

        return {
            'data': data,
            'summary': {
                'total_overrun_tasks': len(overrun_data),
                'total_overrun_hours': round(total_overrun_hours, 2),
                'avg_overrun_percentage': round(total_overrun_hours / total_tasks * 100, 2) if total_tasks else 0
            }
        }

    def _get_timesheet_compliance_data(self):
        developers = self.env['res.users'].search([('share', '=', False)])
        colors = self._get_chart_colors()
        secondary_colors = self._get_chart_colors('secondary')
        current_date = fields.Date.today()
        start_date = current_date - timedelta(days=30)

        on_time_count = delayed_count = missing_count = 0

        for developer in developers:
            timesheet_entries = self.env['account.analytic.line'].search([
                ('user_id', '=', developer.id),
                ('project_id', '!=', False),
                ('date', '>=', start_date),
                ('date', '<=', current_date)
            ])

            if not timesheet_entries:
                missing_count += 1
                continue

            expected_days = len([d for d in self._get_working_days(start_date, current_date)])
            actual_days = len(set(timesheet_entries.mapped('date')))
            compliance_rate = actual_days / expected_days if expected_days else 0

            if compliance_rate >= 0.9:
                on_time_count += 1
            elif compliance_rate >= 0.5:
                delayed_count += 1
            else:
                missing_count += 1

        total = on_time_count + delayed_count + missing_count
        data = {
            'labels': ['On Time', 'Delayed', 'Missing'],
            'datasets': [{
                'label': 'Timesheet Compliance',
                'data': [
                    round((on_time_count / total) * 100, 1) if total else 0,
                    round((delayed_count / total) * 100, 1) if total else 0,
                    round((missing_count / total) * 100, 1) if total else 0
                ],
                'backgroundColor': secondary_colors,
                'borderColor': colors,
                'borderWidth': 1
            }]
        }

        return data

    def _get_working_days(self, start_date, end_date):
        working_days = []
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:
                working_days.append(current)
            current += timedelta(days=1)
        return working_days

    def _get_weekly_burn_rate_data(self, start_date, end_date, interval):
        total_weeks = (end_date - start_date).days // 7
        developers = self.env['res.users'].search([('share', '=', False)])
        weeks = [(start_date + timedelta(weeks=i)).strftime('%W') for i in range(total_weeks)]
        colors = self._get_chart_colors()
        secondary_colors = self._get_chart_colors('secondary')

        data = {
            'labels': weeks,
            'datasets': [
                {
                    'label': dev.name,
                    'data': [
                        sum(self.search([
                            ('user_ids', 'in', [dev.id]),
                            ('task_start_date', '>=', start_date + timedelta(weeks=i)),
                            ('task_start_date', '<', start_date + timedelta(weeks=i + 1))
                        ]).mapped('actual_hours'))
                        for i in range(total_weeks)
                    ],
                    'borderColor': colors[i % len(colors)],
                    'backgroundColor': secondary_colors[i % len(secondary_colors)],
                    'tension': 0.1
                }
                for i, dev in enumerate(developers)
            ]
        }
        return data
    def _get_capacity_allocation_data(self, start_date, end_date, interval):
        """
        Get capacity allocation data for developers within the specified date range

        Args:
            start_date: datetime - Start date for data collection
            end_date: datetime - End date for data collection
            interval: str - Time interval ('day', 'week', or 'month')

        Returns:
            dict: Formatted data for capacity allocation chart
        """
        developers = self.env['res.users'].search([('share', '=', False)])

        # Determine the number of intervals based on the selected period
        if interval == 'day':
            intervals = [(end_date - timedelta(days=i)).strftime('%Y-%m-%d')
                         for i in range((end_date - start_date).days + 1)]
        elif interval == 'week':
            intervals = [(end_date - timedelta(weeks=i)).strftime('%Y-%W')
                         for i in range(4)]
        else:  # month
            intervals = [(end_date - timedelta(days=30 * i)).strftime('%Y-%m')
                         for i in range(12)]

        data = {
            'developers': [dev.name for dev in developers],
            'weeks': intervals,
            'data': []
        }

        for dev in developers:
            dev_data = []
            for i, interval_date in enumerate(intervals):
                if interval == 'day':
                    interval_start = datetime.strptime(interval_date, '%Y-%m-%d')
                    interval_end = interval_start + timedelta(days=1)
                elif interval == 'week':
                    year, week = interval_date.split('-')
                    interval_start = datetime.strptime(f'{year}-W{week}-1', '%Y-W%W-%w')
                    interval_end = interval_start + timedelta(weeks=1)
                else:  # month
                    interval_start = datetime.strptime(interval_date, '%Y-%m')
                    interval_end = (interval_start + timedelta(days=32)).replace(day=1)

                tasks = self.search([
                    ('user_ids', 'in', [dev.id]),
                    ('task_start_date', '>=', interval_start),
                    ('task_start_date', '<', interval_end),
                    ('active', '=', True)
                ])

                hours = sum(tasks.mapped('actual_hours') or [0])
                dev_data.append(round(hours, 2))

            data['data'].append(dev_data)

        return data
    # def _get_developer_performance_breakdown(self, start_date, end_date):
    #     developers = self.env['res.users'].search([('share', '=', False)])
    #     data = []
    #     for dev in developers:
    #         # Changed from user_id to user_ids
    #         tasks = self.search([('user_ids', 'in', [dev.id])])
    #         task_types = tasks.mapped('task_type')
    #         categories = {}
    #         for task_type in task_types:
    #             categories[task_type] = {
    #                 'type': task_type,
    #                 'hours': sum(self.search([
    #                     ('user_ids', 'in', [dev.id]),
    #                     ('task_type', '=', task_type)
    #                 ]).mapped('actual_hours'))
    #             }
    #         data.append({
    #             'developer': dev.name,
    #             'categories': list(categories.values())
    #         })
    #     return data
    def _get_task_distribution(self, start_date=False, end_date=False, _logger=None):
        """
        Get task type distribution breakdown for each developer
        """
        if not start_date:
            start_date = fields.Date.today() - timedelta(days=30)
        if not end_date:
            end_date = fields.Date.today()

        # Ensure we have datetime objects
        if isinstance(start_date, str):
            start_date = fields.Date.from_string(start_date)
        if isinstance(end_date, str):
            end_date = fields.Date.from_string(end_date)

        developers = self.env['res.users'].search([
            ('share', '=', False),
            ('active', '=', True)
        ])

        colors = self._get_chart_colors()
        data = []

        # Get all unique task types first
        all_task_types = self.env['project.task'].search([
            ('create_date', '>=', start_date),
            ('create_date', '<=', end_date)
        ]).mapped('task_type')
        all_task_types = list(set(all_task_types))  # Remove duplicates

        for dev in developers:
            try:
                tasks = self.env['project.task'].search([
                    ('user_ids', 'in', [dev.id]),
                    ('create_date', '>=', start_date),
                    ('create_date', '<=', end_date)
                ])

                if not tasks:
                    continue

                categories = []
                for index, task_type in enumerate(all_task_types):
                    type_tasks = tasks.filtered(lambda t: t.task_type == task_type)
                    hours = sum(type_tasks.mapped('actual_hours') or [0.0])

                    if hours > 0:  # Only add categories with hours
                        categories.append({
                            'type': task_type or 'Undefined',
                            'hours': float(hours),
                            'color': colors[index % len(colors)]
                        })

                if categories:  # Only add developer if they have task hours
                    data.append({
                        'developer': dev.name,
                        'categories': categories
                    })
            except Exception as e:
                _logger.error(f"Error processing developer {dev.name}: {str(e)}")
                continue

        return data

    def _get_task_backlog_data(self):
        tasks = self.search([])
        colors = self._get_chart_colors()
        secondary_colors = self._get_chart_colors('secondary')

        data = {
            'labels': ['To Do', 'In Progress', 'Done'],
            'datasets': [{
                'label': 'Task Backlog',
                'data': [
                    len(tasks.filtered(lambda t: not t.stage_id.fold)),
                    len(tasks.filtered(lambda t: not t.stage_id.fold and t.stage_id.sequence > 0)),
                    len(tasks.filtered(lambda t: t.stage_id.fold))
                ],
                'backgroundColor': secondary_colors,
                'borderColor': colors,
                'borderWidth': 1
            }]
        }
        return data



















































# class ProjectTask(models.Model):
#     _inherit = 'project.task'
#
#     task_start_date = fields.Datetime('Start Date')
#     task_end_date = fields.Datetime('End Date')
#     actual_hours = fields.Float('Actual Hours', compute='_compute_actual_hours', store=True)
#     utilization = fields.Float('Utilization %', compute='_compute_utilization', store=True)
#     task_type = fields.Selection([
#         ('coding', 'Coding'),
#         ('bug_fix', 'Bug Fix'),
#         ('testing', 'Testing'),
#         ('review', 'Review'),
#         ('documentation', 'Documentation')
#     ], string='Task Type', default='coding')
#     is_bug = fields.Boolean('Is Bug')
#     bug_reported_date = fields.Datetime('Bug Reported Date')
#     bug_resolution_date = fields.Datetime('Bug Resolution Date')
#     is_overdue = fields.Boolean('Is Overdue', compute='_compute_is_overdue', store=True)
#
#     @api.depends('timesheet_ids.unit_amount')
#     def _compute_actual_hours(self):
#         for task in self:
#             task.actual_hours = sum(task.timesheet_ids.mapped('unit_amount'))
#
#     @api.depends('planned_hours', 'actual_hours')
#     def _compute_utilization(self):
#         for task in self:
#             task.utilization = (task.actual_hours / task.planned_hours * 100) if task.planned_hours else 0
#
#     @api.depends('date_deadline', 'task_end_date')
#     def _compute_is_overdue(self):
#         for task in self:
#             if task.task_end_date and task.date_deadline:
#                 task.is_overdue = task.task_end_date > task.date_deadline
#             else:
#                 task.is_overdue = False
#
#     def _get_random_color(self):
#
#         import random
#         # Generate random RGB values
#         r = random.randint(50, 255)
#         g = random.randint(50, 255)
#         b = random.randint(50, 255)
#
#         return {
#             'background': f'rgba({r}, {g}, {b}, 0.6)',
#             'border': f'rgba({r}, {g}, {b}, 1)'
#         }
#
#     def _get_weekly_developer_utilization(self, start_date, end_date):
#         # Fetch all active employees
#         employees = self.env['hr.employee'].search([('active', '=', True)])
#
#         # Initialize the result structure
#         data = {
#             'labels': [],  # Will store employee names
#             'datasets': [
#                 {
#                     'label': 'Utilization (%)',
#                     'data': [],
#                     'backgroundColor': 'rgba(179, 193, 0, 0.7)',  # Green-yellow color
#                     'borderColor': 'rgba(179, 193, 0, 1)',
#                     'borderWidth': 1,
#                     'type': 'bar'
#                 },
#                 {
#                     'label': 'Logged Hours',
#                     'data': [],
#                     'backgroundColor': 'rgba(206, 210, 204, 0.7)',  # Light gray color
#                     'borderColor': 'rgba(206, 210, 204, 1)',
#                     'borderWidth': 1,
#                     'type': 'bar'
#                 },
#                 {
#                     'label': 'Estimated Hours',
#                     'data': [],
#                     'backgroundColor': 'rgba(35, 40, 45, 0.7)',  # Dark gray color
#                     'borderColor': 'rgba(35, 40, 45, 1)',
#                     'borderWidth': 1,
#                     'type': 'bar'
#                 }
#             ]
#         }
#
#         # For each employee
#         for employee in employees:
#             # Find the related user
#             user = self.env['res.users'].search([('employee_id', '=', employee.id)], limit=1)
#
#             # Add employee name to labels
#             data['labels'].append(employee.name)
#
#             # Fetch tasks assigned to the employee
#             tasks = self.env['project.task'].search([
#                 ('user_ids', 'in', [user.id]) if user else ('id', '=', False),
#                 ('task_start_date', '>=', start_date),
#                 ('task_start_date', '<=', end_date)
#             ])
#
#             # Calculate estimated hours
#             estimated_hours = sum(tasks.mapped('planned_hours'))
#
#             # Fetch logged hours from timesheets
#             timesheets = self.env['account.analytic.line'].search([
#                 ('employee_id', '=', employee.id),
#                 ('date', '>=', start_date),
#                 ('date', '<=', end_date)
#             ])
#             logged_hours = sum(timesheets.mapped('unit_amount'))
#
#             # Calculate utilization percentage
#             utilization_percentage = (logged_hours / estimated_hours * 100) if estimated_hours else 0
#
#             # Add data to datasets
#             data['datasets'][0]['data'].append(round(utilization_percentage, 2))  # Utilization
#             data['datasets'][1]['data'].append(round(logged_hours, 2))  # Logged Hours
#             data['datasets'][2]['data'].append(round(estimated_hours, 2))  # Estimated Hours
#
#         return data
#
#
#     def _get_hours_by_interval(self, user_id, start_date, end_date, interval, hours_field):
#         domain = [
#             ('user_ids', 'in', [user_id]),
#             ('create_date', '>=', start_date),
#             ('create_date', '<=', end_date)
#         ]
#
#         if interval == 'day':
#             groupby = 'create_date:day'
#         elif interval == 'week':
#             groupby = 'create_date:week'
#         else:
#             groupby = 'create_date:month'
#
#         result = self.read_group(
#             domain,
#             [hours_field],
#             [groupby],
#             lazy=False
#         )
#
#         return [r[hours_field] for r in result]
#
    # def _get_developer_performance_breakdown(self, start_date, end_date):
    #     developers = self.env['res.users'].search([('share', '=', False)])
    #     data = []
    #     for dev in developers:
    #         # Changed from user_id to user_ids
    #         tasks = self.search([('user_ids', 'in', [dev.id])])
    #         task_types = tasks.mapped('task_type')
    #         categories = {}
    #         for task_type in task_types:
    #             categories[task_type] = {
    #                 'type': task_type,
    #                 'hours': sum(self.search([
    #                     ('user_ids', 'in', [dev.id]),
    #                     ('task_type', '=', task_type)
    #                 ]).mapped('actual_hours'))
    #             }
    #         data.append({
    #             'developer': dev.name,
    #             'categories': list(categories.values())
    #         })
    #     return data
#
#
#     def _get_bug_resolution_data(self, start_date, end_date, interval):
#         end_date = fields.Datetime.now()
#         start_date = end_date - timedelta(weeks=12)
#
#         bug_tasks = self.search([
#             ('is_bug', '=', True),
#             ('bug_resolution_date', '>=', start_date),
#             ('bug_resolution_date', '<=', end_date)
#         ])
#
#         data = {
#             'labels': [end_date - timedelta(weeks=i) for i in range(12)],
#             'datasets': [{
#                 'label': 'Bug Resolution Time',
#                 'data': [
#                     sum(bug_tasks.filtered(
#                         lambda t: t.bug_resolution_date >= start_date + timedelta(weeks=i) and
#                                   t.bug_resolution_date < start_date + timedelta(weeks=i + 1)
#                     ).mapped('actual_hours'))
#                     for i in range(12)
#                 ],
#                 'borderColor': 'rgb(75, 192, 192)',
#                 'tension': 0.1
#             }]
#         }
#         return data
#
#     def _get_task_completion_data(self):
#         tasks = self.search([])
#         data = {
#             'labels': ['Completed Early', 'Completed On Time', 'Completed Late'],
#             'datasets': [{
#                 'label': 'Tasks',
#                 'data': [
#                     len(tasks.filtered(lambda t: t.actual_hours < t.planned_hours)),
#                     len(tasks.filtered(lambda t: t.actual_hours == t.planned_hours)),
#                     len(tasks.filtered(lambda t: t.actual_hours > t.planned_hours)),
#                 ],
#                 'backgroundColor': [
#                     'rgba(75, 192, 192, 0.2)',
#                     'rgba(54, 162, 235, 0.2)',
#                     'rgba(255, 99, 132, 0.2)'
#                 ],
#                 'borderColor': [
#                     'rgb(75, 192, 192)',
#                     'rgb(54, 162, 235)',
#                     'rgb(255, 99, 132)'
#                 ],
#                 'borderWidth': 1
#             }]
#         }
#         return data
#     def _get_capacity_allocation_data(self, start_date, end_date, interval):
#         """
#         Get capacity allocation data for developers within the specified date range
#
#         Args:
#             start_date: datetime - Start date for data collection
#             end_date: datetime - End date for data collection
#             interval: str - Time interval ('day', 'week', or 'month')
#
#         Returns:
#             dict: Formatted data for capacity allocation chart
#         """
#         developers = self.env['res.users'].search([('share', '=', False)])
#
#         # Determine the number of intervals based on the selected period
#         if interval == 'day':
#             intervals = [(end_date - timedelta(days=i)).strftime('%Y-%m-%d')
#                          for i in range((end_date - start_date).days + 1)]
#         elif interval == 'week':
#             intervals = [(end_date - timedelta(weeks=i)).strftime('%Y-%W')
#                          for i in range(4)]
#         else:  # month
#             intervals = [(end_date - timedelta(days=30 * i)).strftime('%Y-%m')
#                          for i in range(12)]
#
#         data = {
#             'developers': [dev.name for dev in developers],
#             'weeks': intervals,
#             'data': []
#         }
#
#         for dev in developers:
#             dev_data = []
#             for i, interval_date in enumerate(intervals):
#                 if interval == 'day':
#                     interval_start = datetime.strptime(interval_date, '%Y-%m-%d')
#                     interval_end = interval_start + timedelta(days=1)
#                 elif interval == 'week':
#                     year, week = interval_date.split('-')
#                     interval_start = datetime.strptime(f'{year}-W{week}-1', '%Y-W%W-%w')
#                     interval_end = interval_start + timedelta(weeks=1)
#                 else:  # month
#                     interval_start = datetime.strptime(interval_date, '%Y-%m')
#                     interval_end = (interval_start + timedelta(days=32)).replace(day=1)
#
#                 tasks = self.search([
#                     ('user_ids', 'in', [dev.id]),
#                     ('task_start_date', '>=', interval_start),
#                     ('task_start_date', '<', interval_end),
#                     ('active', '=', True)
#                 ])
#
#                 hours = sum(tasks.mapped('actual_hours') or [0])
#                 dev_data.append(round(hours, 2))
#
#             data['data'].append(dev_data)
#
#         return data
#
#     def _get_project_progress_data(self):
#         projects = self.env['project.project'].search([('active', '=', True)])
#         # Return the data in the correct format
#         return {
#             'labels': [project.name for project in projects],
#             'datasets': [
#                 {
#                     'label': 'Completed Tasks',
#                     'data': [len(project.task_ids.filtered(lambda t: t.stage_id.fold)) for project in projects],
#                     'backgroundColor': 'rgba(54, 162, 235, 0.6)',
#                     'borderColor': 'rgba(54, 162, 235, 1)',
#                     'borderWidth': 1
#                 },
#                 {
#                     'label': 'Pending Tasks',
#                     'data': [len(project.task_ids.filtered(lambda t: not t.stage_id.fold)) for project in projects],
#                     'backgroundColor': 'rgba(255, 99, 132, 0.6)',
#                     'borderColor': 'rgba(255, 99, 132, 1)',
#                     'borderWidth': 1
#                 }
#             ]
#         }
#
#
#     def _calculate_project_progress(self, project):
#         if not project.task_ids:
#             return 0  # No tasks, so progress is 0%
#         completed = len(project.task_ids.filtered(lambda t: t.stage_id.fold))  # Completed tasks
#         total_tasks = len(project.task_ids)
#         progress = (completed / total_tasks) * 100  # Calculate percentage
#         return round(progress, 2)
#
#     def _get_task_overruns_data(self):
#         tasks = self.search([])
#         overrun_data = {}
#
#         for task in tasks:
#             if task.effective_hours > task.planned_hours:
#                 # Calculate overrun
#                 overrun = task.effective_hours - task.planned_hours
#                 # Determine the key (can be by developer or project)
#                 if task.user_ids:
#                     for user in task.user_ids:
#                         key = f"{user.name} ({task.project_id.name})"
#                         if key not in overrun_data:
#                             overrun_data[key] = {'count': 0, 'overrun_hours': 0.0}
#                         overrun_data[key]['count'] += 1
#                         overrun_data[key]['overrun_hours'] += overrun
#                 else:
#                     key = task.project_id.name
#                     if key not in overrun_data:
#                         overrun_data[key] = {'count': 0, 'overrun_hours': 0.0}
#                     overrun_data[key]['count'] += 1
#                     overrun_data[key]['overrun_hours'] += overrun
#
#         # Calculate total for percentage calculation
#         total_tasks = sum(data['count'] for data in overrun_data.values())
#         total_overrun_hours = sum(data['overrun_hours'] for data in overrun_data.values())
#
#         # Format data for the bar chart
#         labels = list(overrun_data.keys())
#         overrun_count_data = [data['count'] for data in overrun_data.values()]
#         overrun_percentage_data = [
#             round((data['count'] / total_tasks) * 100, 1) if total_tasks else 0
#             for data in overrun_data.values()
#         ]
#
#         data = {
#             'labels': labels,
#             'datasets': [
#                 {
#                     'label': 'Task Overrun Count',
#                     'data': overrun_count_data,
#                     'backgroundColor': 'rgba(54, 162, 235, 0.2)',
#                     'borderColor': 'rgb(54, 162, 235)',
#                     'borderWidth': 1
#                 },
#                 {
#                     'label': 'Overrun Percentage',
#                     'data': overrun_percentage_data,
#                     'type': 'line',
#                     'backgroundColor': 'rgba(255, 99, 132, 0.2)',
#                     'borderColor': 'rgb(255, 99, 132)',
#                     'borderWidth': 2
#                 }
#             ]
#         }
#
#         return {
#             'data': data,
#             'summary': {
#                 'total_overrun_tasks': len(overrun_data),
#                 'total_overrun_hours': round(total_overrun_hours, 2),
#                 'avg_overrun_percentage': round(total_overrun_hours / total_tasks * 100, 2) if total_tasks else 0
#             }
#         }
#
#     def _get_timesheet_compliance_data(self):
#         developers = self.env['res.users'].search([('share', '=', False)])
#         current_date = fields.Date.today()
#         start_date = current_date - timedelta(days=30)  # Last 30 days
#
#         # Initialize counters for compliance statuses
#         on_time_count = delayed_count = missing_count = 0
#
#         for developer in developers:
#             timesheet_entries = self.env['account.analytic.line'].search([
#                 ('user_id', '=', developer.id),
#                 ('project_id', '!=', False),
#                 ('date', '>=', start_date),
#                 ('date', '<=', current_date)
#             ])
#
#             if not timesheet_entries:
#                 missing_count += 1
#                 continue
#
#             # Calculate compliance rate based on daily entries
#             expected_days = len([d for d in self._get_working_days(start_date, current_date)])
#             actual_days = len(set(timesheet_entries.mapped('date')))
#             compliance_rate = actual_days / expected_days if expected_days else 0
#
#             if compliance_rate >= 0.9:
#                 on_time_count += 1
#             elif compliance_rate >= 0.5:
#                 delayed_count += 1
#             else:
#                 missing_count += 1
#
#         total = on_time_count + delayed_count + missing_count
#         data = {
#             'labels': ['On Time', 'Delayed', 'Missing'],
#             'datasets': [{
#                 'label': 'Timesheet Compliance',
#                 'data': [
#                     round((on_time_count / total) * 100, 1) if total else 0,
#                     round((delayed_count / total) * 100, 1) if total else 0,
#                     round((missing_count / total) * 100, 1) if total else 0
#                 ],
#                 'backgroundColor': [
#                     'rgba(75, 192, 192, 0.2)',
#                     'rgba(255, 206, 86, 0.2)',
#                     'rgba(255, 99, 132, 0.2)'
#                 ],
#                 'borderColor': [
#                     'rgb(75, 192, 192)',
#                     'rgb(255, 206, 86)',
#                     'rgb(255, 99, 132)'
#                 ],
#                 'borderWidth': 1
#             }]
#         }
#
#         return data
#
#
#     def _get_working_days(self, start_date, end_date):
#         """Helper method to get working days between two dates, excluding weekends"""
#         working_days = []
#         current = start_date
#         while current <= end_date:
#             # Assuming Monday = 0 and Sunday = 6
#             if current.weekday() < 5:  # Monday to Friday
#                 working_days.append(current)
#             current += timedelta(days=1)
#         return working_days
#
#
#     def _get_weekly_burn_rate_data(self, start_date, end_date,interval):
#         # Calculate number of weeks between start_date and end_date
#         total_weeks = (end_date - start_date).days // 7
#
#         # Get developers to track burn rate for
#         developers = self.env['res.users'].search([('share', '=', False)])
#
#         # Generate week labels for the period
#         weeks = [(start_date + timedelta(weeks=i)).strftime('%W') for i in range(total_weeks)]
#
#         data = {
#             'labels': weeks,
#             'datasets': [
#                 {
#                     'label': dev.name,
#                     'data': [
#                         sum(self.search([
#                             ('user_ids', 'in', [dev.id]),
#                             ('task_start_date', '>=', start_date + timedelta(weeks=i)),
#                             ('task_start_date', '<', start_date + timedelta(weeks=i + 1))
#                         ]).mapped('actual_hours'))
#                         for i in range(total_weeks)
#                     ],
#                     'borderColor': self._get_chart_color(i),
#                     'backgroundColor': self._get_chart_color(i, 0.2),
#                     'tension': 0.1
#                 }
#                 for i, dev in enumerate(developers)
#             ]
#         }
#         return data
#
#     def _get_task_backlog_data(self):
#         tasks = self.search([])
#         data = {
#             'labels': ['To Do', 'In Progress', 'Done'],
#             'datasets': [{
#                 'label': 'Task Backlog',
#                 'data': [
#                     len(tasks.filtered(lambda t: not t.stage_id.fold)),
#                     len(tasks.filtered(lambda t: not t.stage_id.fold and t.stage_id.sequence > 0)),
#                     len(tasks.filtered(lambda t: t.stage_id.fold))
#                 ],
#                 'backgroundColor': [
#                     'rgba(255, 99, 132, 0.2)',
#                     'rgba(54, 162, 235, 0.2)',
#                     'rgba(75, 192, 192, 0.2)'
#                 ],
#                 'borderColor': [
#                     'rgb(255, 99, 132)',
#                     'rgb(54, 162, 235)',
#                     'rgb(75, 192, 192)'
#                 ],
#                 'borderWidth': 1
#             }]
#         }
#         return data
#
#     def _get_chart_color(self, index, alpha=1.0):
#         colors = [
#             'rgba(255, 99, 132, {})'.format(alpha),
#             'rgba(54, 162, 235, {})'.format(alpha),
#             'rgba(255, 206, 86, {})'.format(alpha),
#             'rgba(75, 192, 192, {})'.format(alpha),
#             'rgba(153, 102, 255, {})'.format(alpha),
#             'rgba(255, 159, 64, {})'.format(alpha)
#         ]
#         return colors[index % len(colors)]























