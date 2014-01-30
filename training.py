#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
from trytond.model import Workflow, ModelView, ModelSQL, fields
from trytond.pyson import Eval, Id
from trytond.pool import Pool

STATE = [('draft', 'Draft'),
         ('open', 'Opened'),
         ('closed', 'Closed'),
         ('cancel', 'Canceled'),
         ('done', 'Done'),
         ]

STATES = {
    'readonly': (Eval('state') != 'draft'),
}

DEPENDS = ['active']

SEPARATOR = ' / '

__all__ = ['TrainingCourseCategory', 'TrainingCourseType',
           'TrainingCourse', 'TrainingOffer',
           'TrainingCourseOfferRel']

class TrainingCourseCategory(ModelView, ModelSQL):
    'The category of a course'
    __name__ = 'training.course.category'
    
    name = fields.Char('Full Name')
    description = fields.Text('Description',
                                    translate=True,
                                    help="Allows to the user to write the description of the course type")
    
class TrainingCourseType(ModelView, ModelSQL):
    "The Course's Type"
    __name__ = 'training.course.type'
    
    name = fields.Char('Course Type',  required=True, help="The course type's name")
    active = fields.Boolean('Active', depends = DEPENDS)
    objective = fields.Text('Objective',
                                  help="Allows to the user to write the objectives of the course type",
                                  translate=True,
                                 )
    description = fields.Text('Description',
                                    translate=True,
                                    help="Allows to the user to write the description of the course type")
    
    @staticmethod
    def default_active():
        return True

class TrainingCourse(Workflow, ModelView, ModelSQL):
    'Training Course'
    __name__ = 'training.course'

    name = fields.Char('Name', states=STATES,)
    duration = fields.Integer('Hours Duration', 
            states=STATES,
            help='The hours duration of the course')
    parent = fields.Many2One('training.course',
                                 'Parent Course',
                                 help="The parent course",
                                 states=STATES,
                                 domain=[('state', '=', 'open')])
    childs = fields.One2Many('training.course',
                                       'parent',
                                       "Sub Courses",
                                       states=STATES,
                                       help="A course can be completed with some sub courses")
    code = fields.Char('Code', readonly=True)
    type = fields.Many2One('training.course.type', 'Type',
                                  states=STATES,)
    category = fields.Many2One('training.course.category', 'Course Category',
                               states=STATES,)
    faculty = fields.Many2One('training.faculty', 'Faculty',
                                          help="The faculty who give the course",
                                          states=STATES,)
    description = fields.Text('Description', translate=True, 
                                help="The user can write some descritpion note for this course",
                                states=STATES,)
    state = fields.Selection(STATE, 'State', required=True,
                             readonly=True,
                             help="The state of the course")
    
    @staticmethod
    def default_state():
        return 'draft'
    
    @staticmethod
    def default_duration():
        return 2
    
    @classmethod
    def __setup__(cls):
        super(TrainingCourse, cls).__setup__()
        cls._sql_constraints += [
            ('name_uniq', 'UNIQUE(name)', 'The course must be unique.'),
            ]
        cls._order.insert(0, ('name', 'ASC'))
        cls._transitions |= set((
                ('cancel', 'draft'),
                ('draft', 'cancel'),
                ('draft', 'open'),
                ('open', 'draft'),
                ('open', 'done'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': ~Eval('state').in_(['draft']),
                    },
                'draft': {
                    'invisible': ~Eval('state').in_(['cancel','open']),
                    },
                'open': {
                    'invisible': ~Eval('state').in_(['draft']),
                    },
                'done': {
                    'invisible': Eval('state') != 'open',
                    },
                })
        cls._error_messages.update({
                'wrong_name': ('Invalid course name "%%s": You can not use '
                    '"%s" in name field.' % SEPARATOR),
                })
    
    @classmethod
    def create(cls, vlist):
        Sequence = Pool().get('ir.sequence')
        Config = Pool().get('training.sequences')

        vlist = [x.copy() for x in vlist]
        for values in vlist:
            if not values.get('code'):
                config = Config(1)
                values['code'] = Sequence.get_id(
                    config.course_sequence.id)

        return super(TrainingCourse, cls).create(vlist)

    @classmethod
    def validate(cls, courses):
        super(TrainingCourse, cls).validate(courses)
        cls.check_recursion(courses, rec_name='name')
        for course in courses:
            course.check_name()

    def check_name(self):
        if SEPARATOR in self.name:
            self.raise_user_error('wrong_name', (self.name,))

    def get_rec_name(self, name):
        if self.parent:
            return self.parent.get_rec_name(name) + SEPARATOR + self.name
        return self.name

    @classmethod
    def search_rec_name(cls, name, clause):
        if isinstance(clause[2], basestring):
            values = clause[2].split(SEPARATOR)
            values.reverse()
            domain = []
            field = 'name'
            for name in values:
                domain.append((field, clause[1], name))
                field = 'parent.' + field
            categories = cls.search(domain, order=[])
            return [('id', 'in', [category.id for category in categories])]
        #TODO Handle list
        return [('name',) + tuple(clause[1:])]
            
    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, records):
        pass
    
    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, records):
        pass
    
    @classmethod
    @ModelView.button
    @Workflow.transition('open')
    def open(cls, records):
        cls.set_code(records)
        
    @classmethod
    def set_code(cls, records):
        '''
        Fill the code field with the course sequence
        '''
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('training.sequences')
        config = Config(1)
        for record in records:
            if record.code:
                continue
            code = Sequence.get_id(config.course_sequence.id)
            cls.write([record], {'code': code})
    
    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, records):
        pass

class TrainingOffer(Workflow, ModelView, ModelSQL):
    'Training Offer'
    __name__ = 'training.offer'
    
    name = fields.Many2One('product.template', 'Name', required=True,
                           states=STATES,
                           domain=[('type', '=', 'service'),
                                   ('category', '=', Id('training', 'cat_offer'))],
                           select=True)
    code = fields.Char('Code',
                              states=STATES)
    courses = fields.Many2Many('training.course.offer.rel',
                               'offer', 'course', 'Courses',
                               domain=[('state','=','open')], 
                               states = STATES, help='An offer can contain many courses')
    type = fields.Many2One('training.course.type', 'Type',
                           states=STATES)
    description = fields.Text('Description',
                              states=STATES,
                                    help="Allows to write the description of the offer")
    objective = fields.Text('Objective',
                            states=STATES,
                            help='The objective of the offer will be used by the internet web site')
    requeriments = fields.Text('Requeriments',
                               states=STATES,
                                    help="Allows to write the requeriments of the offer")
    state = fields.Selection(STATE,
                              'State', required=True, readonly=True)

    @classmethod
    def __setup__(cls):
        super(TrainingOffer, cls).__setup__()
        cls._sql_constraints += [
            ('name_uniq', 'UNIQUE(name)', 'The offer must be unique.'),
            ]
        cls._order.insert(0, ('name', 'ASC'))
        cls._transitions |= set((
                ('cancel', 'draft'),
                ('draft', 'cancel'),
                ('draft', 'open'),
                ('open', 'draft'),
                ('open', 'done'),
                ))
        cls._buttons.update({
                'cancel': {
                    'invisible': ~Eval('state').in_(['draft']),
                    },
                'draft': {
                    'invisible': ~Eval('state').in_(['cancel','open']),
                    },
                'open': {
                    'invisible': ~Eval('state').in_(['draft']),
                    },
                'done': {
                    'invisible': Eval('state') != 'open',
                    },
                })
        cls._error_messages.update({
                'wrong_name': ('Invalid course name "%%s": You can not use '
                    '"%s" in name field.' % SEPARATOR),
                })
    
    @classmethod
    def create(cls, vlist):
        Sequence = Pool().get('ir.sequence')
        Config = Pool().get('training.sequences')

        vlist = [x.copy() for x in vlist]
        for values in vlist:
            if not values.get('code'):
                config = Config(1)
                values['code'] = Sequence.get_id(
                    config.offer_sequence.id)

        return super(TrainingOffer, cls).create(vlist)
    
    @staticmethod
    def default_state():
        return 'draft'
        
    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, records):
        pass
    
    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, records):
        pass
    
    @classmethod
    @ModelView.button
    @Workflow.transition('open')
    def open(cls, records):
        cls.set_code(records)
        
    @classmethod
    def set_code(cls, records):
        '''
        Fill the code field with the offer sequence
        '''
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Config = pool.get('training.sequences')
        config = Config(1)
        for record in records:
            if record.code:
                continue
            code = Sequence.get_id(config.offer_sequence.id)
            cls.write([record], {'code': code})
    
    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def done(cls, records):
        pass
    
    def get_rec_name(self, name):
        if self.name:
            return self.name.rec_name


class TrainingCourseOfferRel(ModelSQL):
    'Training Course Offer Relation'
    __name__ = 'training.course.offer.rel'
    _table = 'training_offer_rel'

    offer = fields.Many2One('training.offer', 'Offer', 
                            select=True, required=True, ondelete='CASCADE')
    course = fields.Many2One('training.course', 'Course', 
                             select=True, required=True, ondelete='RESTRICT')
