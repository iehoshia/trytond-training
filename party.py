#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta, date
from trytond.model import ModelView, ModelSQL, fields
from trytond.wizard import Wizard, StateAction, StateView, Button
from trytond.transaction import Transaction
from trytond.pyson import Eval, Not, Bool, PYSONEncoder, Equal
from trytond.pool import Pool

__all__ = ['PartyAddress', 'Party',
           'StudentData', 'FacultyData',
           'StudentNote',
           'PartyNote']

_TYPES = [
    ('phone', 'Phone'),
    ('mobile', 'Mobile'),
    ('fax', 'Fax'),
    ('email', 'E-Mail'),
    ('website', 'Website'),
    ('skype', 'Skype'),
    ('sip', 'SIP'),
    ('irc', 'IRC'),
    ('jabber', 'Jabber'),
    ('personal', 'Personal'),
    ('other', 'Other'),
    ]

_NOTES = [
    ('Llamar', 'Llamar'),
    ('Atender', 'Atender'),
    ('Normal', 'Normal'),
    ]

class PartyAddress(ModelSQL, ModelView):
    'Party Address'
    __name__ = 'party.address'

    relationship = fields.Char(
        'Relationship',
        help='Include the relationship with the person - friend, co-worker,'
        ' brother,...')
    relative_id = fields.Many2One(
        'party.party', 'Contact', domain=[('is_person', '=', True)],
        help='Include link to the relative')

    is_school = fields.Boolean(
        "School", help="Check this box to mark the school address")
    is_work = fields.Boolean(
        "Work", help="Check this box to mark the work address")


class Party(ModelSQL, ModelView):
    'Party'
    __name__ = 'party.party'

    is_person = fields.Boolean(
        'Person',
        on_change_with=['is_person', 'is_student', 'is_faculty'],
        help='Check if the party is a person.')

    is_student = fields.Boolean(
        'Student',
        states={'invisible': Not(Bool(Eval('is_person')))},
        help='Check if the party is a student')

    is_faculty = fields.Boolean(
        'Teacher',
        states={'invisible': Not(Bool(Eval('is_person')))},
        help='Check if the party is a faculty')

    is_institution = fields.Boolean(
        'Institution', help='Check if the party is a Medical Center')
    
    matricule = fields.Char('Matricule',
                                  help="The matricule of the contact")
    education_level = fields.Char('Education Level')
    activation_date = fields.DateTime('Activation date', help='Date of activation of the party')
    
    lastname = fields.Char('Last Name', help='Last Name')
    dpi = fields.Char('DPI Number')
    dob = fields.Date('DoB', help='Date of Birth')
    profession = fields.Char('Profession or Office')

    sex = fields.Selection([
        (None, ''),
        ('m', 'Male'),
        ('f', 'Female'),
        ], 'Sex')

    photo = fields.Binary('Picture')

    marital_status = fields.Selection([
        (None, ''),
        ('s', 'Single'),
        ('m', 'Married'),
        ('c', 'Concubinage'),
        ('w', 'Widowed'),
        ('d', 'Divorced'),
        ('x', 'Separated'),
        ], 'Marital Status', sort=False)

    citizenship = fields.Many2One(
        'country.country', 'Citizenship', help='Country of Citizenship')
    residence = fields.Many2One(
        'country.country', 'Country of Residence', help='Country of Residence')
    alternative_identification = fields.Boolean(
        'Alternative ID', help='Other type of '
        'identification, not the official SSN from this country'
        ' center. Examples : Passport, foreign ID,..')
    internal_user = fields.Many2One(
        'res.user', 'Internal User',
        help='In Training Module is the user (faculty) that logins. When the'
        ' party is a faculty or a training professional, it will be the user'
        ' that maps the faculty\'s party name. It must be present.',
        states={
            'invisible': Not(Bool(Eval('is_faculty'))),
            'required': Bool(Eval('is_faculty')),
            })
    
    notes = fields.One2Many('party.notes', 'party', 'Notes')
    
    last_note = fields.Function(fields.Char('Last Note'), 'get_last_note')

    @classmethod
    def write(cls, parties, vals):
        # We use this method overwrite to make the fields that have a unique
        # constraint get the NULL value at PostgreSQL level, and not the value
        # '' coming from the client

        if vals.get('ref') == '':
            vals['ref'] = None
        return super(Party, cls).write(parties, vals)

    @classmethod
    def create(cls, vlist):
        # We use this method overwrite to make the fields that have a unique
        # constraint get the NULL value at PostgreSQL level, and not the value
        # '' coming from the client

        vlist = [x.copy() for x in vlist]
        for values in vlist:
            if 'ref' in values and not values['ref']:
                values['ref'] = None

        return super(Party, cls).create(vlist)

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls._sql_constraints += [
            ('internal_user_uniq', 'UNIQUE(internal_user)',
                'This faculty is already assigned to a party')]

    def get_rec_name(self, name):
        if self.lastname:
            return self.lastname + ', ' + self.name
        else:
            return self.name

    @classmethod
    def search_rec_name(cls, name, clause):
        field = None
        for field in ('name', 'lastname'):
            parties = cls.search([(field,) + tuple(clause[1:])], limit=1)
            if parties:
                break
        if parties:
            return [(field,) + tuple(clause[1:])]
        return [(cls._rec_name,) + tuple(clause[1:])]
    

    def on_change_with_is_person(self):
        # Set is_person if the party is a training professional or a student
        if (self.is_faculty or self.is_student or self.is_person):
            return True

    @classmethod
    def validate(cls, parties):
        super(Party, cls).validate(parties)
        for party in parties:
            party.check_person()

    def check_person(self):
    # Verify that training professional and student
    # are unchecked when is_person is False

        if not self.is_person and (self.is_student or self.is_faculty):
            self.raise_user_error(
                "The Person field must be set if the party is a faculty"
                " or a student")
    
    @staticmethod
    def default_activation_date():
        now = datetime.now()
        return now
    
    @staticmethod
    def default_is_person():
        return True
    
    @staticmethod
    def default_is_student():
        return True
    
    @staticmethod
    def default_citizenship():
        return 3
    
    @staticmethod
    def default_residence():
        return 3
    
    
    def get_last_note(self, name=None):
        if self.notes:
            if self.notes[0].note_type != None and self.notes[0].value  != None:
                return self.notes[0].note_type + ' '+self.notes[0].value
            else:
                return ''
            
# STUDENT GENERAL INFORMATION
class StudentData(ModelSQL, ModelView):
    'Student related information'
    __name__ = 'training.student'

    # Get the student age in the following format : 'YEARS MONTHS DAYS'
    # It will calculate the age of the student while the student is alive.
    # When the student dies, it will show the age at time of death.

    def student_age(self, name):

        def compute_age_from_dates(student_dob):

            now = datetime.now()

            if (student_dob):
                dob = datetime.strptime(str(student_dob), '%Y-%m-%d')
                delta = relativedelta(now, dob)
                years_months_days = str(delta.years) + 'a ' \
                    + str(delta.months) + 'm ' \
                    + str(delta.days) + 'd'
            else:
                years_months_days = 'No DoB !'

            # Return the age in format y m d when the caller is the field name
            if name == 'age':
                return years_months_days

        return compute_age_from_dates(self.dob)

    name = fields.Many2One(
        'party.party', 'Name', required=True,
        domain=[
            ('is_person', '=', True),
            ('is_student','=',True),
            ],
        help="Person associated to this student")
    lastname = fields.Function(
        fields.Char('Lastname'), 'get_student_lastname',
        searcher='search_student_lastname')
    identification_code = fields.Char(
        'ID', readonly=True,
        help='Student Identifier provided by the Training Center. Is not the'
        ' Social Security Number')
    active = fields.Boolean('Active', select=True)

    current_address = fields.Many2One(
        'party.address', 'Addresses',
        domain=[('party', '=', Eval('name'))],
        depends=['name'],
        help="Use this address for temporary contact information. For example \
        if the student is on vacation, you can put the hotel address. \
        In the case of a Domiciliary Unit, just link it to the name of the \
        contact in the address form.")
    
    notes = fields.One2Many('student.note','student',
                            'Notes')

    photo = fields.Function(fields.Binary('Picture'), 'get_student_photo')

    dob = fields.Function(fields.Date('DoB'), 'get_student_dob')

    age = fields.Function(fields.Char('Age'), 'student_age')
    
    phone = fields.Function(fields.Char('Phone'), 'get_phone')
    mobile = fields.Function(fields.Char('Mobile'), 'get_mobile')
    fax = fields.Function(fields.Char('Fax'), 'get_fax')
    email = fields.Function(fields.Char('E-Mail'), 'get_email')
    website = fields.Function(fields.Char('Website'), 'get_website')

    sex = fields.Function(fields.Selection([
        ('m', 'Male'),
        ('f', 'Female'),
        ], 'Sex'), 'get_student_sex')

    marital_status = fields.Function(
        fields.Selection([
            (None, ''),
            ('s', 'Single'),
            ('m', 'Married'),
            ('c', 'Concubinage'),
            ('w', 'Widowed'),
            ('d', 'Divorced'),
            ('x', 'Separated'),
            ], 'Marital Status', sort=False), 'get_student_marital_status')

    blood_type = fields.Selection([
        (None, ''),
        ('A', 'A'),
        ('B', 'B'),
        ('AB', 'AB'),
        ('O', 'O'),
        ], 'Blood Type', sort=False)

    rh = fields.Selection([
        (None, ''),
        ('+', '+'),
        ('-', '-'),
        ], 'Rh')


    @classmethod
    def __setup__(cls):
        super(StudentData, cls).__setup__()
        cls._sql_constraints = [
            ('name_uniq', 'UNIQUE(name)', 'The Student already exists !'),
        ]

    @staticmethod
    def default_active():
        return True
    
    def get_student_dob(self, name):
        return self.name.dob

    def get_student_sex(self, name):
        return self.name.sex

    def get_student_photo(self, name):
        return self.name.photo

    def get_student_marital_status(self, name):
        return self.name.marital_status

    def get_student_lastname(self, name):
        return self.name.lastname
    
    def get_phone(self, name):
        return self.name.phone

    def get_mobile(self, name):
        return self.name.mobile
    
    def get_fax(self, name):
        return self.name.fax
    
    def get_email(self, name):
        return self.name.email
    
    def get_website(self, name):
        return self.name.website
    
    @classmethod
    def search_student_lastname(cls, name, clause):
        res = []
        value = clause[2]
        res.append(('name.lastname', clause[1], value))
        return res

    @classmethod
    def create(cls, vlist):
        Sequence = Pool().get('ir.sequence')
        Config = Pool().get('training.sequences')

        vlist = [x.copy() for x in vlist]
        for values in vlist:
            if not values.get('identification_code'):
                config = Config(1)
                values['identification_code'] = Sequence.get_id(
                    config.student_sequence.id)

        return super(StudentData, cls).create(vlist)

    
    def get_rec_name(self, name):
        if self.name.lastname:
            return self.name.lastname + ', ' + self.name.name
        else:
            return self.name.name

    # Search by the patient name, lastname or SSN
    @classmethod
    def search_rec_name(cls, name, clause):
        field = None
        for field in ('name', 'lastname'):
            parties = cls.search([(field,) + tuple(clause[1:])], limit=1)
            if parties:
                break
        if parties:
            return [(field,) + tuple(clause[1:])]
        return [(cls._rec_name,) + tuple(clause[1:])]
    
# STUDENT GENERAL INFORMATION
class FacultyData(ModelSQL, ModelView):
    'Faculty related information'
    __name__ = 'training.faculty'

    # Get the student age in the following format : 'YEARS MONTHS DAYS'
    # It will calculate the age of the student while the student is alive.
    # When the student dies, it will show the age at time of death.

    def student_age(self, name):

        def compute_age_from_dates(student_dob):

            now = datetime.now()

            if (student_dob):
                dob = datetime.strptime(str(student_dob), '%Y-%m-%d')
                delta = relativedelta(now, dob)
                years_months_days = str(delta.years) + 'a ' \
                    + str(delta.months) + 'm ' \
                    + str(delta.days) + 'd.'
            else:
                years_months_days = 'No DoB !'

            # Return the age in format y m d when the caller is the field name
            if name == 'age':
                return years_months_days

        return compute_age_from_dates(self.dob)

    name = fields.Many2One(
        'party.party', 'Name', required=True,
        domain=[
            ('is_faculty', '=', True),
            ('is_person', '=', True),
            ],
        states={'readonly': Bool(Eval('name'))},
        help="Person associated to this student")

    lastname = fields.Function(
        fields.Char('Lastname'), 'get_student_lastname',
        searcher='search_student_lastname')

    identification_code = fields.Char(
        'ID', readonly=True,
        help='Faculty Identifier provided by the Training Center. Is not the'
        ' Social Security Number')
    active = fields.Boolean('Active', select=True)

    current_address = fields.Many2One(
        'party.address', 'Temp. Addr',
        domain=[('party', '=', Eval('name'))],
        depends=['name'],
        help="Use this address for temporary contact information. For example \
        if the student is on vacation, you can put the hotel address. \
        In the case of a Domiciliary Unit, just link it to the name of the \
        contact in the address form.")
    
    photo = fields.Function(fields.Binary('Picture'), 'get_student_photo')

    dob = fields.Function(fields.Date('DoB'), 'get_student_dob')

    age = fields.Function(fields.Char('Age'), 'student_age')

    sex = fields.Function(fields.Selection([
        ('m', 'Male'),
        ('f', 'Female'),
        ], 'Sex'), 'get_student_sex')

    marital_status = fields.Function(
        fields.Selection([
            (None, ''),
            ('s', 'Single'),
            ('m', 'Married'),
            ('c', 'Concubinage'),
            ('w', 'Widowed'),
            ('d', 'Divorced'),
            ('x', 'Separated'),
            ], 'Marital Status', sort=False), 'get_student_marital_status')

    blood_type = fields.Selection([
        (None, ''),
        ('A', 'A'),
        ('B', 'B'),
        ('AB', 'AB'),
        ('O', 'O'),
        ], 'Blood Type', sort=False)

    rh = fields.Selection([
        (None, ''),
        ('+', '+'),
        ('-', '-'),
        ], 'Rh')

    @classmethod
    def __setup__(cls):
        super(FacultyData, cls).__setup__()
        cls._sql_constraints = [
            ('name_uniq', 'UNIQUE(name)', 'The Faculty already exists !'),
        ]
        
    @staticmethod
    def default_active():
        return True

    def get_student_dob(self, name):
        return self.name.dob

    def get_student_sex(self, name):
        return self.name.sex

    def get_student_photo(self, name):
        return self.name.photo

    def get_student_marital_status(self, name):
        return self.name.marital_status

    def get_student_lastname(self, name):
        return self.name.lastname

    @classmethod
    def search_student_lastname(cls, name, clause):
        res = []
        value = clause[2]
        res.append(('name.lastname', clause[1], value))
        return res

    @classmethod
    def create(cls, vlist):
        Sequence = Pool().get('ir.sequence')
        Config = Pool().get('training.sequences')

        vlist = [x.copy() for x in vlist]
        for values in vlist:
            if not values.get('identification_code'):
                config = Config(1)
                values['identification_code'] = Sequence.get_id(
                    config.faculty_sequence.id)

        return super(StudentData, cls).create(vlist)

    def get_rec_name(self, name):
        if self.name.lastname:
            return self.name.lastname + ', ' + self.name.name
        else:
            return self.name.name
    
    @classmethod
    def search_rec_name(cls, name, clause):
        field = None
        for field in ('name', 'lastname'):
            parties = cls.search([(field,) + tuple(clause[1:])], limit=1)
            if parties:
                break
        if parties:
            return [(field,) + tuple(clause[1:])]
        return [(cls._rec_name,) + tuple(clause[1:])]
        
class PartyNote(ModelSQL, ModelView):
    "Party Notes"
    __name__ = 'party.notes'

    type = fields.Selection(_TYPES, 'Type', required=True)
    note_type = fields.Selection(_NOTES, 'Note', required=True)
    value = fields.Char('Value', select=True)
    comment = fields.Text('Comment')
    party = fields.Many2One('party.party', 'Party',
        ondelete='CASCADE', select=True)
    date = fields.Date('Date', readonly=True, select=True)

    @classmethod
    def __setup__(cls):
        super(PartyNote, cls).__setup__()
        cls._order.insert(0, ('id', 'DESC'))

    @staticmethod
    def default_type():
        return 'personal'

    @staticmethod
    def default_note_type():
        return 'Normal'
    
    @staticmethod
    def default_active():
        return True
    
    @staticmethod
    def default_date():
        Date_ = Pool().get('ir.date')
        return Date_.today()


class StudentNote(ModelSQL, ModelView):
    "Student Notes"
    __name__ = 'student.note'

    type = fields.Selection(_TYPES, 'Type', required=True)
    note_type = fields.Selection(_NOTES, 'Note', required=True)
    value = fields.Char('Value', select=True)
    comment = fields.Text('Comment')
    student = fields.Many2One('training.student', 'Student',
        ondelete='CASCADE', select=True)
    date = fields.Date('Date', readonly=True, select=True)

    @classmethod
    def __setup__(cls):
        super(StudentNote, cls).__setup__()
        cls._order.insert(0, ('date', 'ASC'))

    @staticmethod
    def default_type():
        return 'personal'

    @staticmethod
    def default_active():
        return True
    
    @staticmethod
    def default_date():
        Date_ = Pool().get('ir.date')
        return Date_.today()
