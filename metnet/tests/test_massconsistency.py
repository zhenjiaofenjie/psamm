#!/usr/bin/env python

import unittest

from metnet.metabolicmodel import MetabolicModel
from metnet.database import DictDatabase
from metnet import massconsistency
from metnet.datasource.modelseed import parse_reaction
from metnet.reaction import Compound

try:
    from metnet.lpsolver import cplex
except ImportError:
    cplex = None


class TestMassConsistency(unittest.TestCase):
    """Test mass consistency using a simple model"""

    def setUp(self):
        # TODO use mock model instead of actual model
        self.database = DictDatabase()
        self.database.set_reaction('rxn_1', parse_reaction('=> (2) |A|'))
        self.database.set_reaction('rxn_2', parse_reaction('|A| <=> |B|'))
        self.database.set_reaction('rxn_3', parse_reaction('|A| => |D|'))
        self.database.set_reaction('rxn_4', parse_reaction('|A| => |C|'))
        self.database.set_reaction('rxn_5', parse_reaction('|C| => |D|'))
        self.database.set_reaction('rxn_6', parse_reaction('|D| =>'))
        self.model = MetabolicModel.load_model(self.database, self.database.reactions)

        self.solver = cplex.Solver()

    @unittest.skipIf(cplex is None, 'solver not available')
    def test_mass_consistent_is_consistent(self):
        exchange = { 'rxn_1', 'rxn_6' }
        self.assertTrue(massconsistency.is_consistent(
            self.model, self.solver, exchange, set()))

    @unittest.skipIf(cplex is None, 'solver not available')
    def test_mass_inconsistent_is_consistent(self):
        exchange = { 'rxn_1', 'rxn_6' }
        self.database.set_reaction('rxn_7', parse_reaction('|D| => (2) |C|'))
        self.model.add_reaction('rxn_7')
        self.assertFalse(massconsistency.is_consistent(
            self.model, self.solver, exchange, set()))

    @unittest.skipIf(cplex is None, 'solver not available')
    def test_mass_consistent_reactions_returns_compounds(self):
        exchange = { 'rxn_1', 'rxn_6' }
        _, compounds = massconsistency.check_reaction_consistency(
            self.model, exchange=exchange, solver=self.solver)
        for c, value in compounds:
            self.assertIn(c, self.model.compounds)
            self.assertGreaterEqual(value, 1.0)

    @unittest.skipIf(cplex is None, 'solver not available')
    def test_mass_consistent_reactions_returns_reactions(self):
        exchange = { 'rxn_1', 'rxn_6' }
        reactions, _ = massconsistency.check_reaction_consistency(
            self.model, exchange=exchange, solver=self.solver)
        for r, residual in reactions:
            self.assertIn(r, self.model.reactions)


class TestMassConsistencyZeroMass(unittest.TestCase):
    """Test mass consistency using a model with zero-mass compound"""

    def setUp(self):
        # TODO use mock model instead of actual model
        self.database = DictDatabase()
        self.database.set_reaction('rxn_1', parse_reaction(
            '|A| + |B| => |C|'))
        self.database.set_reaction('rxn_2', parse_reaction(
            '|C| + |Z| => |A| + |B|'))
        self.model = MetabolicModel.load_model(
            self.database, self.database.reactions)

        self.solver = cplex.Solver()

    def test_is_consistent_with_zeromass(self):
        consistent = massconsistency.is_consistent(
            self.model, solver=self.solver, zeromass={'Z'})
        self.assertTrue(consistent)

    def test_compound_consistency_with_zeromass(self):
        compounds = dict(massconsistency.check_compound_consistency(
            self.model, solver=self.solver, zeromass={'Z'}))
        self.assertEquals(compounds[Compound('Z')], 0)
        for c, value in compounds.iteritems():
            if c.name != 'Z':
                self.assertGreaterEqual(value, 1)

    def test_reaction_consistency_with_zeromass(self):
        reactions, _ = massconsistency.check_reaction_consistency(
            self.model, solver=self.solver, zeromass={'Z'})
        reactions = dict(reactions)

        for r, value in reactions.iteritems():
            self.assertEqual(value, 0)


if __name__ == '__main__':
    unittest.main()
