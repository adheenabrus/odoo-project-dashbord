# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from datetime import datetime, timedelta


class ProjectDashboard(http.Controller):
    @http.route('/project/dashboard/data', type='json', auth='user')
    def get_dashboard_data(self, start_date=None, end_date=None):
        Projects = request.env['project.project']
        Tasks = request.env['project.task']

        # Convert date strings to datetime objects
        try:
            if start_date:
                start_date = datetime.strptime(start_date, '%Y-%m-%d')
            else:
                # Default to 30 days ago if no start date provided
                start_date = datetime.now() - timedelta(days=30)

            if end_date:
                end_date = datetime.strptime(end_date, '%Y-%m-%d')
            else:
                # Default to current date if no end date provided
                end_date = datetime.now()
        except ValueError:
            # Fallback to default date range if parsing fails
            start_date = datetime.now() - timedelta(days=30)
            end_date = datetime.now()

        # Get data within the selected period
        domain = [
            ('create_date', '>=', start_date),
            ('create_date', '<=', end_date),
            ('active', '=', True)
        ]

        active_projects = Projects.search([('active', '=', True)])
        active_tasks = Tasks.search([])
        team_members = active_projects.mapped('user_id')

        # Calculate total hours from timesheets
        total_hours = sum(active_tasks.mapped('effective_hours') or [0])

        values = {
            'summary': {
                'total_projects': len(active_projects),
                'active_tasks': len(active_tasks.filtered(lambda t: not t.stage_id.fold)),
                'total_hours': round(total_hours, 2),
                'team_members': len(team_members),
            },
            'weekly_developer_utilization': Tasks._get_weekly_developer_utilization(start_date, end_date),
            'task_distribution': Tasks._get_task_distribution(start_date, end_date),
            'bug_resolution': Tasks._get_bug_resolution_data(start_date, end_date, 'day'),
            'capacity_allocation': Tasks._get_capacity_allocation_data(start_date, end_date, 'day'),
            'recent_projects': self._get_recent_projects(),
            'task_completion': Tasks._get_task_completion_data(start_date, end_date),
            'project_progress': Tasks._get_project_progress_data(),
            'timesheet_compliance': Tasks._get_timesheet_compliance_data(),
            'task_overruns': Tasks._get_task_overruns_data(),
            'weekly_burn_rate': Tasks._get_weekly_burn_rate_data(start_date, end_date, 'day'),
            'task_backlog': Tasks._get_task_backlog_data()
        }
        return values


    def _get_recent_projects(self):
        Project = request.env['project.project']
        projects = Project.search([('active', '=', True)], limit=5, order='create_date desc')
        return [{
            'name': project.name,
            'progress': self._calculate_project_progress(project),
            'tasks': len(project.task_ids),
            'hours': round(sum(project.task_ids.mapped('effective_hours') or [0]), 2),
            'status': self._get_project_status(project),
            'status_class': self._get_status_class(self._get_project_status(project))
        } for project in projects]

    def _calculate_project_progress(self, project):
        if not project.task_ids:
            return 0
        completed = len(project.task_ids.filtered(lambda t: t.stage_id.fold))
        return round((completed / len(project.task_ids)) * 100, 2)


    def _get_project_status(self, project):
        if not project.task_ids:
            return 'draft'
        if all(task.stage_id.fold for task in project.task_ids):
            return 'completed'
        if any(task.is_overdue for task in project.task_ids):
            return 'delayed'
        return 'in_progress'

    def _get_status_class(self, status):
        status_classes = {
            'draft': 'bg-secondary',
            'completed': 'bg-success',
            'delayed': 'bg-danger',
            'in_progress': 'bg-info'
        }
        return status_classes.get(status, 'bg-secondary')


























































    # def _get_recent_projects(self, start_date, end_date):
    #     Project = request.env['project.project']
    #     domain = [
    #         ('active', '=', True),
    #         ('create_date', '>=', start_date),
    #         ('create_date', '<=', end_date)
    #     ]
    #     projects = Project.search(domain, limit=5, order='create_date desc')
    #     return [{
    #         'name': project.name,
    #         'progress': self._calculate_project_progress(project),
    #         'tasks': len(project.task_ids),
    #         'hours': round(sum(project.task_ids.mapped('effective_hours') or [0]), 2),
    #         'status': self._get_project_status(project),
    #         'status_class': self._get_status_class(self._get_project_status(project))
    #     } for project in projects]
    #
    # def _calculate_project_progress(self, project):
    #     if not project.task_ids:
    #         return 0
    #     completed = len(project.task_ids.filtered(lambda t: t.stage_id.fold))
    #     return round((completed / len(project.task_ids)) * 100, 2)
    #
    # def _get_project_status(self, project):
    #     if not project.task_ids:
    #         return 'draft'
    #     if all(task.stage_id.fold for task in project.task_ids):
    #         return 'completed'
    #     if any(task.is_overdue for task in project.task_ids):
    #         return 'delayed'
    #     return 'in_progress'
    #
    # def _get_status_class(self, status):
    #     status_classes = {
    #         'draft': 'bg-secondary',
    #         'completed': 'bg-success',
    #         'delayed': 'bg-danger',
    #         'in_progress': 'bg-info'
    #     }
    #     return status_classes.get(status, 'bg-secondary')







# class ProjectDashboard(http.Controller):
#     @http.route('/project/dashboard/data', type='json', auth='user')
#     def get_dashboard_data(self):
#         Projects = request.env['project.project']
#         Tasks = request.env['project.task']
#
#         active_projects = Projects.search([('active', '=', True)])
#         active_tasks = Tasks.search([])
#         team_members = active_projects.mapped('user_id')
#
#         # Calculate total hours from timesheets
#         total_hours = sum(active_tasks.mapped('effective_hours') or [0])
#
#         values = {
#             'summary': {
#                 'total_projects': len(active_projects),
#                 'active_tasks': len(active_tasks.filtered(lambda t: not t.stage_id.fold)),
#                 'total_hours': round(total_hours, 2),
#                 'team_members': len(team_members),
#             },
#             'weekly_developer_utilization': Tasks._get_weekly_developer_utilization(),
#             'developer_performance': Tasks._get_developer_performance_breakdown(),
#             'bug_resolution': Tasks._get_bug_resolution_data(),
#             'capacity_allocation': Tasks._get_capacity_allocation_data(),
#             'recent_projects': self._get_recent_projects(),
#             'task_completion': self._get_task_completion_data(),
#             'project_progress': self._get_project_progress_data(),
#             'timesheet_compliance': self._get_timesheet_compliance_data(),
#             'task_overruns': self._get_task_overruns_data(),
#             'weekly_burn_rate': self._get_weekly_burn_rate_data(),
#             'task_backlog': self._get_task_backlog_data()
#         }
#         return values
#
#     def _get_recent_projects(self):
#         Project = request.env['project.project']
#         projects = Project.search([('active', '=', True)], limit=5, order='create_date desc')
#         return [{
#             'name': project.name,
#             'progress': self._calculate_project_progress(project),
#             'tasks': len(project.task_ids),
#             'hours': round(sum(project.task_ids.mapped('effective_hours') or [0]), 2),
#             'status': self._get_project_status(project),
#         } for project in projects]
#
#     def _calculate_project_progress(self, project):
#         if not project.task_ids:
#             return 0
#         completed = len(project.task_ids.filtered(lambda t: t.stage_id.fold))
#         return round((completed / len(project.task_ids)) * 100, 2)
#
#     def _get_project_status(self, project):
#         if not project.task_ids:
#             return 'draft'
#         if all(task.stage_id.fold for task in project.task_ids):
#             return 'completed'
#         if any(task.is_overdue for task in project.task_ids):
#             return 'delayed'
#         return 'in_progress'




































# class ProjectDashboard(http.Controller):
#     @http.route('/project/dashboard/data', type='json', auth='user')
#     def get_dashboard_data(self):
#         Projects = request.env['project.project']
#         Tasks = request.env['project.task']
#
#         # Get all active projects
#         active_projects = Projects.search([('active', '=', True)])
#         # Get all active tasks
#         active_tasks = Tasks.search([])
#         # Get team members (users assigned to projects)
#         team_members = active_projects.mapped('user_id')
#
#         # Calculate total hours from timesheets
#         total_hours = sum(active_tasks.mapped('effective_hours') or [0])
#
#         values = {
#             'summary': {
#                 'total_projects': len(active_projects),
#                 'active_tasks': len(active_tasks.filtered(lambda t: not t.stage_id.fold)),
#                 'total_hours': round(total_hours, 2),
#                 'team_members': len(team_members),
#             },
#             'recent_projects': self._get_recent_projects(),
#             'developer_utilization': request.env['project.task'].get_developer_utilization_data(),
#             'task_completion': request.env['project.task'].get_task_completion_data(),
#             'project_progress': request.env['project.task'].get_project_progress_data(),
#             'timesheet_compliance': request.env['project.task'].get_timesheet_compliance_data(),
#         }
#         return values
#
#     def _get_recent_projects(self):
#         Project = request.env['project.project']
#         projects = Project.search([('active', '=', True)], limit=5, order='create_date desc')
#         result = []
#
#         for project in projects:
#             # Calculate task statistics
#             all_tasks = project.task_ids
#             completed_tasks = all_tasks.filtered(lambda t: t.stage_id.fold)
#
#             # Calculate progress
#             progress = 0
#             if all_tasks:
#                 progress = round((len(completed_tasks) / len(all_tasks)) * 100, 2)
#
#             # Calculate total hours
#             total_hours = sum(all_tasks.mapped('effective_hours') or [0])
#
#             # Determine project status
#             status = 'in_progress'
#             if not all_tasks:
#                 status = 'draft'
#             elif all(task.stage_id.fold for task in all_tasks):
#                 status = 'completed'
#             elif project.user_id and not project.active:
#                 status = 'cancelled'
#
#             result.append({
#                 'name': project.name,
#                 'progress': progress,
#                 'tasks': len(all_tasks),
#                 'hours': round(total_hours, 2),
#                 'status': status,
#                 'status_class': self._get_status_class(status)
#             })
#
#         return result
#
#     def _get_status_class(self, state):
#         status_classes = {
#             'draft': 'badge-secondary',
#             'in_progress': 'badge-primary',
#             'pending': 'badge-warning',
#             'completed': 'badge-success',
#             'cancelled': 'badge-danger'
#         }
#         return status_classes.get(state, 'badge-secondary')












#
# class ProjectDashboard(http.Controller):
#     @http.route('/project/dashboard/data', type='json', auth='user')
#     def get_dashboard_data(self):
#         return {
#             'developer_utilization': request.env['project.task'].get_developer_utilization_data(),
#             'task_completion': request.env['project.task'].get_task_completion_data(),
#             'project_progress': request.env['project.task'].get_project_progress_data(),
#             'timesheet_compliance': request.env['project.task'].get_timesheet_compliance_data(),
#         }

