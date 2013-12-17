#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from decimal import Decimal
from datetime import datetime, timedelta, date
import operator
from itertools import izip, groupby
from sql import Column, Literal
from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateView, StateAction, StateTransition, \
    Button
from trytond.report import Report
from trytond.tools import reduce_ids
from trytond.pyson import Eval, PYSONEncoder, Date, Id
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond import backend

STATE = [('draft', 'Draft'),
         ('opened', 'Opened'),
         ('confirmed', 'Confirmed'),
         ('in_progress', 'In Progress'),
         ('closed', 'Closed'),
         ('cancelled', 'Cancelled')]

STATES = {
    'readonly': (Eval('state') != 'draft'),
}

STATES_CONFIRMED = {
    'readonly': (Eval('state') != 'draft'),
    'required': (Eval('state') == 'confirmed'),
}

class TrainingCourseCategory(ModelView, ModelSQL):
    'The category of a course'
    __name__ = 'training.course_category'
    
    name = fields.Char('Full Name')
    
class TrainingCourseType(ModelView, ModelSQL):
    "The Course's Type"
    __name__ = 'training.course_type'
    
    name = fields.Char('Course Type',  required=True, help="The course type's name")
    objective = fields.Text('Objective',
                                  help="Allows to the user to write the objectives of the course type",
                                  translate=True,
                                 )
    description = fields.Text('Description',
                                    translate=True,
                                    help="Allows to the user to write the description of the course type")

class TrainingCourseTheme(ModelView, ModelSQL):
    'Course Theme'
    __name__ = 'training.course.theme'

    name = fields.Char('Name', required=True)
    active = fields.Boolean('Active')
    priority = fields.Integer('Priority')
    description = fields.Text('Description',
                                    help="Allows to write the description of the theme")

    def default_action(self):
        return True
    
    def default_priority(self):
        return 0

class TrainingTemplateCourse(ModelView, ModelSQL):
    'Training Template Course'
    __name__ = 'training.template.course'
    
    name = fields.Char('Name')
    category = fields.Many2One('training.course.category','Category', required=True)
    format = fields.Many2One('training.format', 'Format')
    force_format = fields.Boolean('Force Format')
    language = fields.Char('Language')
    force_language = fields.Boolean('Force Language') 
    goal = fields.Text('Goal')
    descrition = fields.Text('Description')
    requirement = fields.Text('Requirement')

class TrainingCourse(ModelView, ModelSQL):
    'Training Course'
    __name__ = 'training.course'

    name = fields.Many2One('product.template', 'Name',
            domain=[
            ('type', '=', 'service'), 
            ('category', '=', Id('courses'),
            )], select=True)
    
    splitted_by = fields.Char('Splitted by', required=True)
    duration = fields.Integer('Hours Duration', help='The hours duration of the course')
    parent = fields.Many2One('training.course',
                                 'Parent Course',
                                 help="The parent course",
                                 readonly=True,
                                 domain="[('state_course', '=', 'validated')]")
    childs = fields.One2Many('training.course',
                                       'parent',
                                       "Sub Courses",
                                       help="A course can be completed with some sub courses")
    sequence = fields.Integer('Sequence')
    course_type = fields.Many2One('training.course_type', 'Type')
    category = fields.Many2One('training.course_category', 'Course Category')
    faculty = fields.Many2One('training.faculty', 'Faculty',
                                          help="The faculty who give the course")
    internal_note = fields.Text('Note', translate=True, 
                                help="The user can write some internal note for this course")
    state = fields.selection(STATE, 'State', required=True,
                                          help="The state of the course")
    active = fields.Boolean('Active')
    
    @staticmethod
    def default_state(self):
        return 'draft'
    
    @staticmethod
    def default_duration(self):
        return 2
    
    @staticmethod
    def default_active(self):
        return True
    
    @classmethod
    def __setup__(cls):
        super(TrainingCourse, cls).__setup__()
        cls._sql_constraints += [
            ('name_uniq', 'UNIQUE(name)', 'The course must be unique.'),
            ]

class TrainingOfferFormat(ModelView, ModelSQL):
    'The delivery format of the offer or session'
    __name__ = 'training.offer.format'

    name = fields.Char('Name', required=True, help="The format's name of the offer")
    active = fields.Boolean('Active')
    
    @staticmethod
    def default_active(self):
        return True

class TrainingOffer(ModelView, ModelSQL):
    'Offer'
    __name__ = 'training.offer'
    
    name = fields.Many2One('product.product', 'Name', required=True,
                           domain=[('type', '=', 'service'), 
                                   ('category', '=', Id('hotel', 'cat_rooms'))],)
    type = fields.Many2One('training.course_type', 'Type')
    courses = fields.Many2Many('training.course.offer.rel', 
                               'offer', 'course', 'Courses', help='An offer can contain many courses')
    objective = fields.Text('Objective',
                            help='The objective of the course will be used by the internet web site')
    description = fields.Text('Description',
                                    help="Allows to write the description of the course")
    requeriments = fields.Text('Requeriments',
                                    help="Allows to write the requeriments of the course")
    management = fields.Text('Management',
                                    help="Allows to write the management of the course")
    sequence = fields.Integer('Sequence')
    format = fields.Many2One('training.offer.format', 'Format', required=True,
                                    help="Delivery format of the course")
    state = fields.Selection(STATE,
                              'State', required=True)
    theme = fields.Many2One('training.course.theme', 'Theme')
    notification_note = fields.Text('Notification Note', help='This note will be show on notification emails')
    is_certification = fields.Boolean('Is a certification?', help='Indicate is this Offer is a Certification Offer')

    @staticmethod
    def default_state(self):
        return 'draft'
    
    @staticmethod
    def default_kind(self):
        return 'standard'
    
    @staticmethod
    def default_is_certification(self):
        return True

class TrainingCourseOfferRel(ModelSQL):
    'Training Course Offer Relation'
    __name__ = 'training.course.offer.rel'

    course = fields.Many2One('training.course', 'Course', required=True, ondelete='CASCADE')
    offer = fields.Many2One('training.offer', 'Offer', required=True, ondelete='RESTRICT')  
