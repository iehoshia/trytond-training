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

STATES = {
    'readonly': (Eval('state') != 'draft'),
}

STATES_CONFIRMED = {
    'readonly': (Eval('state') != 'draft'),
    'required': (Eval('state') == 'confirmed'),
}

GUARANTEE = [
    ('payment', 'Payment'),
    ('voucher', 'Voucher'),
    ('credit_card', 'Credit Card'),
    ('letter', 'Letter'),
    ]

class TrainingConfigContactFunction(ModelView, ModelSQL):
    'Training Config Contact Function'
    __name__ = 'training.config.contact.function'

    kind = fields.Selection([('standard','Course')], 'Kind', required=True)
    function = fields.Char('Function', required=True)
    
    @classmethod
    def __setup__(cls):
        super(TrainingConfigContactFunction, cls).__setup__()
        cls._sql_constraints += [
            ('kind_funtion_uniq', 'UNIQUE(kind, function)', 'The kind must be unique.'),
            ]

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
    min_limit = fields.Integer('Minimum Threshold',
                                     required=True,
                                     help="The minimum threshold is the minimum for this type of course")
    max_limit =  fields.Integer('Maximum Threshold',
                                     required=True,
                                     help="The maximum threshold is the maximum for this type of course")

    #def _check_limits(self, cr, uid, ids, context=None):
    #    obj = self.browse(cr, uid, ids)[0]
    #    return obj.min_limit <= obj.max_limit

    #_constraints = [
    #    (_check_limits,
    #     'The minimum limit is greater than the maximum limit',
    #     ['min_limit', 'max_limit']),
    #]


class TrainingTemplateCourse(ModelView, ModelSQL):
    'Training Template Course'
    __name__ = 'training.template.course'
    
    name = fields.Char('Name')
    category = fields.Many2One('training.course.category','Category', required=True)
    format = fields.Many2One('training.format', 'Format')
    force_format = fields.Boolean('Force Format')# visible/editable only if format is not empty): force that all sessions of course have the course's format
    language = fields.Char('Language')
    force_language = fields.Boolean('Force Language') #, visible/editable only if language is not empty): force that all sessions of course have the course's language
    sessions = fields.One2Many( 'training.template.session')# or M2M with 'sequence' in M2M class and allow to select/add sessions as M2M fields)
    goal = fields.Text('Goal')
    descrition = fields.Text('Description')
    requirement = fields.Text('Requirement')
    
class TrainingCourseTheme(ModelView, ModelSQL):
    'Course Theme'
    __name__ = 'training.course.theme'

    name = fields.Char('Name', required=True)
    active = fields.Boolean('Active')
    parent_id = fields.Many2One('training.course.theme', 'Parent')
    priority = fields.Integer('Priority')
    description = fields.Text('Description',
                                    help="Allows to write the description of the theme")

    def default_action(self):
        return True
    
    def default_priority(self):
        return 0

class TrainingCourseKind(ModelView, ModelSQL):
    'Training Course King'
    __name__ = 'training.course.kind'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', translate=True, required=True)

    
    @classmethod
    def __setup__(cls):
        super(TrainingCourseKind, cls).__setup__()
        cls._sql_constraints += [
            ('uniq_code', 'UNIQUE(code)', 'The code of this kind must be unique.')
            ]

def training_course_kind_compute(obj, cr, uid, context=None):
    proxy = obj.pool.get('training.course.kind')
    return [(kind.code, kind.name) for kind in proxy.browse(cr, uid, proxy.search(cr, uid, []))] or []

class TrainingCourseOfferRel(ModelSQL):
    'Training Course Offer Relation'
    __name__ = 'training.course.offer.rel'

    course = fields.Many2One('training.course', 'Course', required=True, ondelete='CASCADE')
    offer = fields.Many2One('training.offer', 'Offer', required=True, ondelete='CASCADE')  
    
class TrainingCourse(ModelView, ModelSQL):
    'Course'
    __name__ = 'training.course'

    def _total_duration_compute(self, cr, uid, ids, name, args, context=None):
        res = dict.fromkeys(ids, 0.0)

        if 'offer_id' in context:
            context = context.copy()
            del context['offer_id']

        for course in self.browse(cr, uid, ids, context=context):
            res[course.id] = reduce(lambda acc, child: acc + child.duration, course.course_ids, 0.0)

        return res

    #def _has_support(self, cr, uid, ids, name, args, context=None):
    #    res = dict.fromkeys(ids, 0)
    #    cr.execute("SELECT res_id, count(1) "
    #               "FROM ir_attachment "
    #               "WHERE res_id in ("+ ",".join(['%s'] * len(ids)) + ")"
    #               "AND res_model = 'training.course' "
    #               "AND is_support = %s "
    #               "GROUP BY res_id",
    #               ids + [True],
    #    )
    #    res.update(dict([(x[0], bool(x[1])) for x in cr.fetchall()]))

    #    return res

    def action_workflow_pending(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state_course' : 'pending'}, context=context)

    def test_course_for_validation(self, cr, uid, ids, context=None):
        return True

    def _duration_compute(self, cr, uid, ids, name, args, context=None):
        res = dict.fromkeys(ids, 0.0)

        if 'offer_id' in context:
            context=context.copy()
            del context['offer_id']

        for course in self.browse(cr, uid, ids, context=context):
            res[course.id] = len(course.course_ids) and course.duration_with_children or course.duration_without_children

        return res

    def _with_children_compute(self, cr, uid, ids, name, args, context=None):
        res = dict.fromkeys(ids, 0.0)

        if 'offer_id' in context:
            context = context.copy()
            del context['offer_id']

        for course in self.browse(cr, uid, ids, context=context):
            res[course.id] = bool(len(course.course_ids))

        return res

    def _attachment_compute(self, cr, uid, ids, fieldnames, args, context=None):
        res = dict.fromkeys(ids, [])
        proxy = self.pool.get('ir.attachment')
        for course in self.browse(cr, uid, ids, context=context):
            res[course.id] = proxy.search(cr, uid,
                                          [('res_model', '=', self._name),
                                           ('res_id', '=', course.id),
                                           ('is_support', '=', 1)],
                                          context=context
                                         )

        return res

    def _get_support(self, cr, uid, ids, context=None):
        proxy = self.pool.get('ir.attachment')
        attach_ids = proxy.search(cr, uid, [('id', 'in', ids),('res_model', '=', 'training.course'),('is_support', '=', 1)], context=context)
        res = set()
        for attach in proxy.browse(cr, uid, attach_ids, context=context):
            res.add(attach.res_id)

        return list(res)

    splitted_by = fields.Char('Splitted by', required=True)
    themes = fields.Many2Many('training.course.theme', 'training_course_theme_rel', 'course',
                                      'theme', 'Theme')
    duration = fields.Integer('Hours Duration', help='The hours duration of the course')
    parent = fields.Many2One('training.course',
                                 'Parent Course',
                                 help="The parent course",
                                 readonly=True,
                                 domain="[('state_course', '=', 'validated')]")
    courses = fields.One2Many('training.course',
                                       'parent',
                                       "Sub Courses",
                                       help="A course can be completed with some subcourses")
    sequence = fields.Integer('Sequence')
    course_type = fields.Many2One('training.course_type', 'Type')
    category = fields.Many2One('training.course_category', 'Product Line')
    faculties = fields.Many2Many('teachers-courses', 'training_course_job_rel', 
                                 'course', 'faculty', 'Faculty',
                                          select=1,
                                          help="The lecturers who give the course"),
    internal_note = fields.Text('Note', translate=True, 
                                help="The user can write some internal note for this course")
    kind = fields.Selection([('standard','Standard')],
                                 'Kind',
                                 required=True,
                                 select=2,
                                 help="The kind of course")
    state = fields.selection([('draft', 'Draft'),
                                           ('pending', 'Ask Review'),
                                           ('deprecated', 'Deprecated'),
                                           ('validated', 'Validated'),
                                          ],
                                          'State',
                                          required=True,
                                          select=1,
                                          help="The state of the course"
                                         )

    long_name = fields.Char('Long Name',
                        help='Allows to show the long name of the course for the external view')
    
    def default_state(self):
        return 'draft'
    
    def default_duration(self):
        return 1
    
    def default_kind(self):
        return 'standard'
    
    def _check_duration(self, cr, uid, ids, context=None):
        this = self.browse(cr, uid, ids[0], context=context)
        #return (this.duration > 0.0 or this.duration_without_children > 0.0 or this.duration_with_children > 0.0)
        return this.duration_without_children > 0.0

    def create(self, cr, uid, values, context=None):
        if 'category_id' in values:
            proxy = self.pool.get('training.course_category')
            values['parent_id'] = proxy.browse(cr, uid, values['category_id'], context).analytic_account_id.id
        return super(TrainingCourse, self).create(cr, uid, values, context)

    def write(self, cr, uid, ids, values, context=None):
        if 'category_id' in values:
            proxy = self.pool.get('training.course_category')
            values['parent_id'] = proxy.browse(cr, uid, values['category_id'], context).analytic_account_id.id
        return super(TrainingCourse, self).write(cr, uid, ids, values, context)

    def search(self, cr, uid, domain, offset=0, limit=None, order=None, context=None, count=False):
        link_id = context and context.get('link_id', False) or False
        has_master_course = context and ('master_course' in context) or False

        if link_id:

            course = self.browse(cr, uid, link_id, context=context)

            reference_id = course.reference_id and course.reference_id.id or course.id

            res = super(TrainingCourse, self).search(cr, uid, [('reference_id', '=', reference_id)], context=context)
            if course.reference_id:
                res += [course.reference_id.id]

            return list(set(res))

        if has_master_course:
            return list(set(super(TrainingCourse, self).search(cr, uid, [('reference_id', '!=', False)], context=context)))

        offer_id = context and context.get('offer_id', False) or False

        if offer_id:
            proxy = self.pool.get('training.course.offer.rel')
            ids = proxy.search(cr, uid, [('offer_id', '=', offer_id)], context=context)
            return [rel.course_id.id for rel in proxy.browse(cr, uid, ids, context=context)]

        return super(TrainingCourse, self).search(cr, uid, domain, offset=offset,
                                                   limit=limit, order=order, context=context, count=count)

    def action_workflow_validate(self, cr, uid, ids, context=None):
        proxy = self.pool.get('training.course.pending')
        for course_id in ids:
            pending_ids = proxy.search(cr, uid, [('course_id', '=', course_id)], context=context)
            proxy.write(cr, uid, pending_ids, {'todo' : 1}, context=context)

        return self.write(cr, uid, ids, {'state_course' : 'validated'}, context=context)

    #def reset_to_draft(self, cr, uid, ids, context=None):
    #    workflow = netsvc.LocalService('workflow')

    #    for oid in ids:
    #        workflow.trg_create(uid, self._name, oid, cr)

    #    return self.write(cr, uid, ids, {'state' : 'draft'}, context=context)

class TrainingOfferPlubicTarget(ModelView, ModelSQL):
    __name__ = 'training.offer.public.target'
    
    name = fields.Char('Name',
                           translate=True,
                           help="Allows to the participants to select a course whose can participate")
    note = fields.text('Target Audience', translate=True)

    _sql_constraints = [
        ('target_name', 'unique (name)', 'The name must be unique !')
    ]

class TrainingOfferKing(ModelView, ModelSQL):
    'Training Offer Kind'
    __name__ = 'training.offer.kind'

    code = fields.Char('Code', required=True),
    name = fields.Char('Name', translate=True, required=True)

    _sql_constraints = [
        ('uniq_code', 'UNIQUE(code)', "The code of this kind must be unique."),
    ]

class TrainingOfferFormat(ModelView, ModelSQL):
    'The delivery format of the offer or session'
    __name__ = 'training.offer.format'

    name = fields.Char('Name', required=True, help="The format's name of the offer or session")
    active = fields.Boolean('Active')
    

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
    sequence = fields.Integer('Sequence', help="Allows to order the offers by its importance"),
    format = fields.Many2One('training.offer.format', 'Format', required=True,
                                    help="Delivery format of the course")
    state = fields.Selection([('draft', 'Draft'),
                              ('validated', 'Validated'),
                              ('deprecated', 'Deprecated')],
                              'State', required=True)
    themes = fields.Many2Many('training.course.theme', 'training_offer_them_rel', 'offer',
                                      'theme', 'Theme')
    notification_note = fields.Text('Notification Note', help='This note will be show on notification emails')
    is_certification = fields.Boolean('Is a certification?', help='Indicate is this Offer is a Certification Offer')
    is_planned = fields.Boolean('Is Planned')

    def default_state(self):
        return 'draft'
    
    def default_kind(self):
        return 'standard'
    
    def default_is_certification(self):
        return False
        
    def action_workflow_deprecate(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state' : 'deprecated'}, context=context)
