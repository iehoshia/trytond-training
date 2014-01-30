# This file is part of subscription module of Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .configuration import *
from .party import *
from .training import *

def register():
    Pool.register(
        TrainingSequences,
        PartyAddress,
        Party,
        StudentData,
        FacultyData,
        TrainingCourseCategory,
        TrainingCourseType,
        TrainingOffer,
        TrainingCourse,
        TrainingCourseOfferRel,
        StudentNote, 
        PartyNote,
        module='training', type_='model')
