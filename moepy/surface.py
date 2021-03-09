# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/04-surface-estimation.ipynb (unless otherwise specified).

__all__ = ['PicklableFunction', 'get_fit_kwarg_sets', 'fit_models']

# Cell
import pandas as pd
import numpy as np

import seaborn as sns
import matplotlib.pyplot as plt

import os
import pickle
import FEAutils as hlp
from ipypb import track

from moepy import lowess, eda

# Cell
import copy
import types
import marshal

class PicklableFunction:
    def __init__(self, fun):
        self._fun = fun

    def __call__(self, *args, **kwargs):
        return self._fun(*args, **kwargs)

    def __getstate__(self):
        try:
            return pickle.dumps(self._fun)
        except Exception:
            return marshal.dumps((self._fun.__code__, self._fun.__name__))

    def __setstate__(self, state):
        try:
            self._fun = pickle.loads(state)
        except Exception:
            code, name = marshal.loads(state)
            self._fun = types.FunctionType(code, {}, name)

        return

def get_fit_kwarg_sets():
    fit_kwarg_sets = [
        # quantile lowess
        {
            'name': f'p{int(q*100)}',
            'lowess_kwargs': {'reg_func': PicklableFunction(lowess.calc_quant_reg_betas)},
            'q': q,
        }
        for q in np.linspace(0.1, 0.9, 9)

        # standard lowess
    ] + [{'name': 'average'}]

    return fit_kwarg_sets

# Cell
def fit_models(model_definitions, models_dir):
    for model_parent_name, model_spec in model_definitions.items():
        for fit_kwarg_set in track(model_spec['fit_kwarg_sets'], label=model_parent_name):
            run_name = fit_kwarg_set.pop('name')
            model_name = f'{model_parent_name}_{run_name}'

            if f'{model_name}.pkl' not in os.listdir(models_dir):
                smooth_dates = lowess.SmoothDates()

                reg_dates = pd.date_range(
                    model_spec['reg_dates_start'],
                    model_spec['reg_dates_end'],
                    freq=model_spec['reg_dates_freq']
                )

                smooth_dates.fit(
                    model_spec['x'],
                    model_spec['y'],
                    dt_idx=model_spec['dt_idx'],
                    reg_dates=reg_dates,
                    frac=model_spec['frac'],
                    threshold_value=model_spec['dates_smoothing_value'],
                    threshold_units=model_spec['dates_smoothing_units'],
                    num_fits=model_spec['num_fits'],
                    **fit_kwarg_set
                )

                model_fp = f'{models_dir}/{model_name}.pkl'
                pickle.dump(smooth_dates, open(model_fp, 'wb'))

                del smooth_dates