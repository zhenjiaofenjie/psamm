#!/usr/bin/env python

import argparse
from metabolicmodel import MetabolicDatabase
import fastcore
import fluxanalysis

if __name__ == '__main__':
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run FastGapFill on a metabolic model')
    parser.add_argument('reactionlist', type=argparse.FileType('r'), help='Model definition')
    parser.add_argument('--database', required=True, metavar='reactionfile', action='append',
                        type=argparse.FileType('r'),
                        help='Reaction definition list to usa as database')
    args = parser.parse_args()

    database = MetabolicDatabase.load_from_files(*args.database)
    model = database.load_model_from_file(args.reactionlist)

    # Run Fastcc and print the inconsistent set
    print 'Calculating Fastcc consistent subset...'
    consistent_core = fastcore.fastcc(model, 0.001)
    print 'Result: |A| = {}, |A| = {}'.format(len(consistent_core), consistent_core)

    # Run Fastcore and print the induced reaction set
    model_complete = model.copy()
    for rxnid in database.reactions:
        model_complete.add_reaction(rxnid)

    print 'Calculating Fastcore induced set with consistent core...'
    core = consistent_core | { 'Biomass' }

    induced = fastcore.fastcore(model_complete, core, 0.001)
    print 'Result: |A| = {}, A = {}'.format(len(induced), induced)
    added_reactions = induced - core
    print 'Extended: |E| = {}, E = {}'.format(len(added_reactions), added_reactions)

    # Load bounds on exchange reactions
    #model.load_exchange_limits()

    print 'Flux balance on original model maximizing Biomass...'
    for rxnid, flux in sorted(fluxanalysis.flux_balance(model, 'Biomass')):
        print '{}\t{}'.format(rxnid, flux)

    print 'Flux balance on induced model maximizing Biomass...'
    model_induced = model.copy()
    for rxnid in induced:
        model_induced.add_reaction(rxnid)
    for rxnid, flux in sorted(fluxanalysis.flux_balance(model_induced, 'Biomass')):
        reaction_class = 'Dbase'
        if rxnid in core:
            reaction_class = 'Core'
        elif rxnid in model.reaction_set:
            reaction_class = 'Model'
        print '{}\t{}\t{}'.format(rxnid, reaction_class, flux)