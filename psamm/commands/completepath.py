# This file is part of PSAMM.
#
# PSAMM is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# PSAMM is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PSAMM.  If not, see <http://www.gnu.org/licenses/>.
#
# Copyright 2014-2017  Jon Lund Steffensen <jon_steffensen@uri.edu>

from __future__ import unicode_literals

import logging
import argparse

from six import text_type, iteritems
from ..reaction import Reaction, Direction
from ..command import (Command, MetabolicMixin, SolverCommandMixin,
                       FilePrefixAppendAction)
from ..gapfill import gapfill, GapFillError
from ..datasource.reaction import parse_compound
from ..gapfilling import create_extended_sink_source_model
from ..lpsolver import lp
from ..fastgapfill import fastcore

logger = logging.getLogger(__name__)


class CompletePathCommand(MetabolicMixin, SolverCommandMixin, Command):
    """Run the CompletePath method on the model."""
    @classmethod
    def init_parser(cls, parser):
        parser.add_argument(
            '--compound', metavar='compound', action=FilePrefixAppendAction,
            type=parse_compound, default=[],
            help='Select compounds to try to unblock')
        parser.add_argument(
            '--penalty', metavar='file', type=argparse.FileType('r'),
            help='List of penalty scores for database reactions')
        parser.add_argument(
            '--db-penalty', metavar='penalty', type=float,
            help='Default penalty for database reactions')
        parser.add_argument(
            '--tp-penalty', metavar='penalty', type=float,
            help='Default penalty for transport reactions')
        parser.add_argument(
            '--source-penalty', metavar='penalty', type=float,
            help='Default penalty for exchange reactions')
        parser.add_argument(
            '--sink-penalty', metavar='penalty', type=float,
            help='Default penalty for exchange reactions')
        parser.add_argument(
            '--epsilon', type=float, default=1e-5,
            help='Threshold for reaction flux')
        parser.add_argument(
            '--no-fba-sinks', action='store_true',
            help='removed implicit sinks from the final CompletePath FBA')
        parser.add_argument(
            '--allow-bounds-expansion', action='store_true',
            help=('Allow GapFill to propose expansion of flux bounds. This'
                  ' includes turning irreversible reactions reversible.'))
        parser.add_argument(
            '--print-gaps', action='store_true',
            help='Print out gap-filling output')
        parser.add_argument(
            '--fastgapfill', action='store_true',
            help='Print out gap-filling output')
        super(CompletePathCommand, cls).init_parser(parser)

    def run(self):
        """Run CompletePath command"""

        # Load compound information
        def compound_name(id):
            if id not in self._model.compounds:
                return id
            return self._model.compounds[id].properties.get('name', id)

        # Reaction gene information
        def reaction_genes_string(id):
            if id not in self._model.reactions:
                return 'No Gene'
            return self._model.reactions[id].properties.get('genes', '')

        # Calculate penalty if penalty file exists
        penalties = {}
        if self._args.penalty is not None:
            for line in self._args.penalty:
                line, _, comment = line.partition('#')
                line = line.strip()
                if line == '':
                    continue
                rxnid, penalty = line.split(None, 1)
                penalties[rxnid] = float(penalty)

        core = set(self._mm.reactions)

        solver = self._get_solver(integer=True)
        default_comp = self._model.default_compartment
        epsilon = self._args.epsilon
        v_max = float(self._model.default_flux_limit)

        blocked = set()
        for compound in self._args.compound:
            if compound.compartment is None:
                compound = compound.in_compartment(default_comp)
            blocked.add(compound)

        if len(blocked) > 0:
            logger.info('Unblocking compounds: {}...'.format(
                ', '.join(text_type(c) for c in sorted(blocked))))
        else:
            logger.info(
                'Unblocking all compounds in model. Use --compound option to'
                ' unblock specific compounds.')
            blocked = set(self._mm.compounds)

        exclude = set()
        if self._model.biomass_reaction is not None:
            exclude.add(self._model.biomass_reaction)

        # Add exchange and transport reactions to database
        model_complete, weights = create_extended_sink_source_model(
            self._model,
            db_penalty=self._args.db_penalty,
            source_penalty=self._args.source_penalty,
            sink_penalty=self._args.sink_penalty,
            tp_penalty=self._args.tp_penalty,
            penalties=penalties)
        for i in self._args.compound:
            reaction_id = 'Compound_Production'
            reaction_ex = Reaction(Direction.Forward, {i: -1})
            model_complete.database.set_reaction(reaction_id, reaction_ex)
            model_complete.add_reaction(reaction_id)

        if self._args.fastgapfill:
            core1 = set(['Compound_Production'])
            added_reactions = fastcore(model_complete, core1, epsilon, solver, scaling=1e5, weights=weights)
        else:
            logger.info('Searching for reactions to fill gaps')
            try:
                added_reactions, no_bounds_reactions = gapfill(
                    model_complete, core, blocked, exclude, solver=solver,
                    epsilon=epsilon, v_max=v_max, weights=weights,
                    implicit_sinks=False,
                    allow_bounds_expansion=self._args.allow_bounds_expansion)
            except GapFillError as e:
                self._log_epsilon_and_fail(epsilon, e)

        if self._args.print_gaps:
            #This should not be model_complete: this should be self._model
            for reaction_id in sorted(model_complete.reactions):
                rx = model_complete.get_reaction(reaction_id)
                rxt = rx.translated_compounds(compound_name)
                print('{}\t{}\t{}\t{}'.format(reaction_id, 'Model', 0, rxt))

            for rxnid in sorted(added_reactions):
                rx = model_complete.get_reaction(rxnid)
                rxt = rx.translated_compounds(compound_name)
                print('{}\t{}\t{}\t{}'.format(
                    rxnid, 'Add', weights.get(rxnid, 1), rxt))

            for rxnid in sorted(no_bounds_reactions):
                rx = model_complete.get_reaction(rxnid)
                rxt = rx.translated_compounds(compound_name)
                print('{}\t{}\t{}\t{}'.format(
                    rxnid, 'Remove bounds', weights.get(rxnid, 1), rxt))

        else:
            sinks = self._args.no_fba_sinks
            model_rxn_list = []
            model_cpd_list = []
            mm = self._model.create_metabolic_model()
            for i in mm.reactions:
                model_rxn_list.append(i)
            for j in added_reactions:
                for k in model_complete.reactions:
                    if k == j:
                        for l in model_complete.get_reaction(k).compounds:
                            model_cpd_list.append(l[0])
                model_rxn_list.append(j)
            for compound_id in self._args.compound:
                print('#Results for Compound {}'.format(compound_id))
                result = pathway_extraction(model_complete,
                                            model_rxn_list, model_cpd_list,
                                            compound_id, sinks,
                                            solver=solver)

                for rxnid, flux, rx in sorted(result):
                    if abs(flux) > self._args.epsilon:
                        rx_trans = rx.translated_compounds(compound_name)
                        if rxnid == 'Compound_Production':
                            obj = (rxnid, flux, rx_trans,
                                   'Compound Production Sink')
                            print('{}\t{}\t{}\t{}'.format(rxnid, flux, rx_trans,
                                  'Compound Production Sink'))
                            continue
                        if rxnid in mm.reactions:
                            genes = reaction_genes_string(rxnid)
                        else:
                            genes = 'Gapfilling Reaction'
                        print('{}\t{}\t{}\t{}'.format(
                            rxnid, flux, rx_trans, genes))
                #logger.info('Compound Production Flux: {}'.format(obj[1]))

    def _log_epsilon_and_fail(self, epsilon, exc):
        msg = ('Finding blocked compounds failed with epsilon set to {}. Try'
               ' lowering the epsilon value to reduce artifical constraints on'
               ' the model.'.format(epsilon))
        self.fail(msg, exc)


def pathway_extraction(metabolic_model, model_rxns,
                       model_cpd_list, compound, sinks, solver):
    """Extract the production pathway for a compound after gap-filling.

    Uses an extended model and reactions identified through the
    gapfilling procedure to create a new LP problem and maximize
    the production of a target compound. This function will generate
    an LP problem with implicit sinks for all compounds except for
    ones involved in the gap-filling reactions. An L1 minimized FBA problem
    is then solved and the result is a flux based synthesis pathway for a
    specific compound. This returns a reaction ID, flux value, and reaction
    entry for each reaction in the metabolic model.

    Args:
        model: :class:`psamm.metabolicmodel.MetabolicModel`.
        model_rxns: A list of reaction IDs of all gap-filling and original
            model reactions.
        model_cpds: A list of Compound Entries for each compound involved
            in any gap-filling reactions.
        compound: A compound Id of a compound being unblocked by the
            gap-filling.
    """

    model = metabolic_model.copy()

    for rxn in metabolic_model.reactions:
        if rxn not in model_rxns:
            model.remove_reaction(rxn)

    prob = solver.create_problem()

    v = prob.namespace()

    # Define flux variables
    for reaction_id in model.reactions:
        lower, upper = model.limits[reaction_id]
        v.define([reaction_id], lower=lower, upper=upper)
    # Define constraints
    massbalance_lhs = {compound: 0 for compound in model.compounds}
    for spec, value in iteritems(model.matrix):
            compound, reaction_id = spec
            massbalance_lhs[compound] += v(reaction_id) * value
    for compound, lhs in iteritems(massbalance_lhs):
        if sinks is True:
            prob.add_linear_constraints(lhs == 0)
        else:
            if compound not in model_cpd_list:
                prob.add_linear_constraints(lhs >= 0)
            else:
                prob.add_linear_constraints(lhs >= 0)

    obj_var = v(name='Compound_Production')
    prob.set_objective(obj_var)
    prob.solve(lp.ObjectiveSense.Maximize)
    obj_flux = prob.result.get_value(obj_var)
    prob.add_linear_constraints(obj_var >= obj_flux)

    z = prob.namespace()
    for reaction_id in model.reactions:
        z.define([reaction_id], lower=0)

    _z = z.set(model.reactions)
    _v = v.set(model.reactions)

    prob.add_linear_constraints(_z >= _v, _v >= -_z)

    objective = z.expr(
        (reaction_id, 1)
        for reaction_id in model.reactions)
    prob.set_objective(objective)
    prob.solve(lp.ObjectiveSense.Minimize)

    for reaction_id in model.reactions:
        rxn = model.get_reaction(reaction_id)
        yield reaction_id, prob.result.get_value(v(reaction_id)), rxn