# AUTOGENERATED! DO NOT EDIT! File to edit: nbs/03-lowess.ipynb (unless otherwise specified).

__all__ = ['get_dist', 'get_dist_threshold', 'dist_to_weights', 'get_all_weights', 'vector_to_dist_matrix',
           'get_frac_idx', 'get_dist_thresholds', 'clean_weights', 'dist_2_weights_matrix',
           'get_full_dataset_weights_matrix', 'get_weighting_locs', 'create_dist_matrix', 'num_fits_2_reg_anchors',
           'get_weights_matrix', 'calc_lin_reg_betas', 'fit_regressions', 'check_array', 'lowess_fit_and_predict',
           'calc_robust_weights', 'robust_lowess_fit_and_predict', 'Lowess', 'get_bootstrap_idxs',
           'get_bootstrap_resid_std_devs', 'run_model', 'bootstrap_model', 'get_confidence_interval',
           'pred_to_quantile_loss', 'calc_quant_reg_loss', 'calc_quant_reg_betas', 'quantile_model',
           'calc_timedelta_dists', 'construct_dt_weights', 'fit_external_weighted_ensemble', 'get_ensemble_preds',
           'SmoothDates']

# Cell
import pandas as pd
import numpy as np

import seaborn as sns
import matplotlib.pyplot as plt
from collections.abc import Iterable
from sklearn import linear_model

from sklearn.base import BaseEstimator, RegressorMixin
from scipy.optimize import minimize
from scipy import linalg

from timeit import timeit
import FEAutils as hlp
from ipypb import track

from moepy import eda

# Cell
get_dist = lambda X, x: np.abs(X - x)

# Cell
def get_dist_threshold(dist, frac=0.4):
    frac_idx = int(np.ceil(len(dist)*frac))
    dist_threshold = sorted(dist)[frac_idx]

    return dist_threshold

# Cell
dist_to_weights = lambda dist, dist_threshold=1: (1 - ((np.abs(dist)/dist_threshold).clip(0, 1) ** 3)) ** 3

# Cell
def get_all_weights(x, frac=0.4):
    all_weights = []

    for i in range(len(x)):
        weights = get_weights(x, x[i], frac=frac)
        all_weights += [weights]

    all_weights = np.array(all_weights)

    return all_weights

# Cell
vector_to_dist_matrix = lambda x: np.abs(x.reshape(-1, 1) - x.reshape(1, -1))

# Cell
get_frac_idx = lambda x, frac: int(np.ceil(len(x) * frac)) - 1

# Cell
get_dist_thresholds = lambda x, frac_idx, dist_matrix: np.sort(dist_matrix)[:, frac_idx]

# Cell
def clean_weights(weights):
    weights = weights/weights.sum(axis=0) # We'll then normalise the weights so that for each model they sum to 1 for a single data point
    weights = np.where(~np.isfinite(weights), 0, weights) # And remove any non-finite values

    return weights

def dist_2_weights_matrix(dist_matrix, dist_thresholds):
    weights = dist_to_weights(dist_matrix, dist_thresholds.reshape(-1, 1))
    weights = clean_weights(weights)

    return weights

# Cell
def get_full_dataset_weights_matrix(x, frac=0.4):
    frac_idx = get_frac_idx(x, frac)

    dist_matrix = vector_to_dist_matrix(x)
    dist_thresholds = get_dist_thresholds(x, frac_idx, dist_matrix)

    weights = dist_2_weights_matrix(dist_matrix, dist_thresholds)

    return weights

# Cell
num_fits_2_reg_anchors = lambda x, num_fits: np.linspace(x.min(), x.max(), num=num_fits)

def get_weighting_locs(x, reg_anchors=None, num_fits=None):
    num_type_2_dist_rows = {
        type(None) : lambda x, num_fits: x.reshape(-1, 1),
        int : lambda x, num_fits: num_fits_2_reg_anchors(x, num_fits).reshape(-1, 1),
    }

    if reg_anchors is None:
        weighting_locs = num_type_2_dist_rows[type(num_fits)](x, num_fits)
    else:
        weighting_locs = reg_anchors.reshape(-1, 1)

    return weighting_locs

def create_dist_matrix(x, reg_anchors=None, num_fits=None):
    weighting_locs = get_weighting_locs(x, reg_anchors=reg_anchors, num_fits=num_fits)
    dist_matrix = np.abs(weighting_locs - x.reshape(1, -1))

    return dist_matrix

# Cell
def get_weights_matrix(x, frac=0.4, weighting_locs=None, reg_anchors=None, num_fits=None):
    frac_idx = get_frac_idx(x, frac)

    if weighting_locs is not None:
        dist_matrix = np.abs(weighting_locs - x.reshape(1, -1))
    else:
        dist_matrix = create_dist_matrix(x, reg_anchors=reg_anchors, num_fits=num_fits)

    dist_thresholds = get_dist_thresholds(x, frac_idx, dist_matrix)
    weights = dist_2_weights_matrix(dist_matrix, dist_thresholds)

    return weights

# Cell
def calc_lin_reg_betas(x, y, weights=None):
    if weights is None:
        weights = np.ones(len(x))

    b = np.array([np.sum(weights * y), np.sum(weights * y * x)])
    A = np.array([[np.sum(weights), np.sum(weights * x)],
                  [np.sum(weights * x), np.sum(weights * x * x)]])

    betas = linalg.solve(A, b)

    return betas

# Cell
check_array = lambda array, x: np.ones(len(x)) if array is None else array

def fit_regressions(x, y, weights=None, reg_func=calc_lin_reg_betas, num_coef=2, **reg_params):
    if weights is None:
        weights = np.ones(len(x))

    n = weights.shape[0]

    y_pred = np.zeros(n)
    design_matrix = np.zeros((n, num_coef))

    for i in range(n):
        design_matrix[i, :] = reg_func(x, y, weights=weights[i, :], **reg_params)

    return design_matrix

# Cell
def lowess_fit_and_predict(x, y, frac=0.4, reg_anchors=None, num_fits=None, x_pred=None):
    weighting_locs = get_weighting_locs(x, reg_anchors=reg_anchors, num_fits=num_fits)
    weights = get_weights_matrix(x, frac=frac, weighting_locs=weighting_locs)
    design_matrix = fit_regressions(x, y, weights)

    if x_pred is None:
        x_pred = x

    point_evals = design_matrix[:, 0] + np.dot(x_pred.reshape(-1, 1), design_matrix[:, 1].reshape(1, -1))
    pred_weights = get_weights_matrix(x_pred, frac=frac, reg_anchors=weighting_locs)

    y_pred = np.multiply(pred_weights, point_evals.T).sum(axis=0)

    return y_pred

# Cell
def calc_robust_weights(y, y_pred, max_std_dev=6):
    residuals = y - y_pred
    std_dev = np.quantile(np.abs(residuals), 0.682)

    cleaned_residuals = np.clip(residuals / (max_std_dev * std_dev), -1, 1)
    robust_weights = (1 - cleaned_residuals ** 2) ** 2

    return robust_weights

# Cell
def robust_lowess_fit_and_predict(x, y, frac=0.4, reg_anchors=None, num_fits=None, x_pred=None, robust_weights=None, robust_iters=3):
    # Identifying the initial loading weights
    weighting_locs = get_weighting_locs(x, reg_anchors=reg_anchors, num_fits=num_fits)
    loading_weights = get_weights_matrix(x, frac=frac, weighting_locs=weighting_locs)

    # Robustifying the weights (to reduce outlier influence)
    if robust_weights is None:
        robust_loading_weights = loading_weights
    else:
        robust_loading_weights = np.multiply(robust_weights, loading_weights)
        robust_loading_weights = robust_loading_weights/robust_loading_weights.sum(axis=0)
        robust_loading_weights = np.where(~np.isfinite(robust_loading_weights), 0, robust_loading_weights)

    # Fitting the model and making predictions
    design_matrix = fit_regressions(x, y, robust_loading_weights)

    if x_pred is None:
        x_pred = x

    point_evals = design_matrix[:, 0] + np.dot(x_pred.reshape(-1, 1), design_matrix[:, 1].reshape(1, -1))
    pred_weights = get_weights_matrix(x_pred, frac=frac, reg_anchors=weighting_locs)

    y_pred = np.multiply(pred_weights, point_evals.T).sum(axis=0)

    # Recursive robust regression
    robust_weights = calc_robust_weights(y, y_pred)

    if robust_iters > 1:
        robust_iters -= 1
        y_pred = robust_lowess_fit_and_predict(x, y, frac=frac, reg_anchors=reg_anchors, num_fits=num_fits, x_pred=x_pred, robust_weights=robust_weights, robust_iters=robust_iters)

    return y_pred

# Cell
class Lowess(BaseEstimator, RegressorMixin):
    def __init__(self, reg_func=calc_lin_reg_betas):
        self.reg_func = reg_func
        self.fitted = False
        return

    def calculate_loading_weights(self, x, reg_anchors=None, num_fits=None, external_weights=None, robust_weights=None):
        # Calculating the initial loading weights
        weighting_locs = get_weighting_locs(x, reg_anchors=reg_anchors, num_fits=num_fits)
        loading_weights = get_weights_matrix(x, frac=self.frac, weighting_locs=weighting_locs)

        # Applying weight adjustments
        if external_weights is None:
            external_weights = np.ones(x.shape[0])

        if robust_weights is None:
            robust_weights = np.ones(x.shape[0])

        weight_adj = np.multiply(external_weights, robust_weights)
        loading_weights = np.multiply(weight_adj, loading_weights)

        # Post-processing weights
        loading_weights = loading_weights/loading_weights.sum(axis=0) # normalising
        loading_weights = np.where(~np.isfinite(loading_weights), 0, loading_weights) # removing non-finite values

        self.weighting_locs = weighting_locs
        self.loading_weights = loading_weights

        return

    def fit(self, x, y, frac=0.4, reg_anchors=None, num_fits=None, external_weights=None, robust_weights=None, robust_iters=3, **reg_params):
        self.frac = frac

        # Solving for the design matrix
        self.calculate_loading_weights(x, reg_anchors=reg_anchors, num_fits=num_fits, external_weights=external_weights, robust_weights=robust_weights)
        self.design_matrix = fit_regressions(x, y, weights=self.loading_weights, reg_func=self.reg_func, **reg_params)

        # Recursive robust regression
        if robust_iters > 1:
            y_pred = self.predict(x)
            robust_weights = calc_robust_weights(y, y_pred)

            robust_iters -= 1
            y_pred = self.fit(x, y, frac=self.frac, reg_anchors=reg_anchors, num_fits=num_fits, external_weights=external_weights, robust_weights=robust_weights, robust_iters=robust_iters, **reg_params)

            return y_pred

        self.fitted = True

        return

    def predict(self, x_pred):
        point_evals = self.design_matrix[:, 0] + np.dot(x_pred.reshape(-1, 1), self.design_matrix[:, 1].reshape(1, -1))
        pred_weights = get_weights_matrix(x_pred, frac=self.frac, reg_anchors=self.weighting_locs)

        y_pred = np.multiply(pred_weights, point_evals.T).sum(axis=0)

        return y_pred

# Cell
def get_bootstrap_idxs(x, bootstrap_bag_size=0.5):
    ## Bag size handling
    assert bootstrap_bag_size>0, 'Bootstrap bag size must be greater than 0'

    if bootstrap_bag_size > 1:
        assert int(bootstrap_bag_size) == bootstrap_bag_size, 'If the bootstrab bag size is not provided as a fraction then it must be an integer'

    else:
        bootstrap_bag_size = int(np.ceil(bootstrap_bag_size*len(x)))

    ## Splitting in-bag and out-of-bag samlpes
    idxs = np.array(range(len(x)))

    ib_idxs = np.sort(np.random.choice(idxs, bootstrap_bag_size, replace=True))
    oob_idxs = np.setdiff1d(idxs, ib_idxs)

    return ib_idxs, oob_idxs

# Cell
def get_bootstrap_resid_std_devs(x, y, bag_size, model=Lowess(), **model_kwargs):
    # Splitting the in- and out-of-bag samples
    ib_idxs, oob_idxs = get_bootstrap_idxs(x, bag_size)

    x_ib, x_oob = x[ib_idxs], x[oob_idxs]
    y_ib, y_oob = y[ib_idxs], y[oob_idxs]

    # Fitting and predicting with the model
    model.fit(x_ib, y_ib, **model_kwargs)

    y_pred = model.predict(x)
    y_ib_pred = model.predict(x_ib)
    y_oob_pred = model.predict(x_oob)

    # Calculating the error
    y_ib_resids = y_ib - y_ib_pred
    ib_resid_std_dev = np.std(np.abs(y_ib_resids))

    y_oob_resids = y_oob - y_oob_pred
    oob_resid_std_dev = np.std(np.abs(y_oob_resids))

    return ib_resid_std_dev, oob_resid_std_dev

# Cell
def run_model(x, y, bag_size, model=Lowess(), x_pred=None, **model_kwargs):
    if x_pred is None:
        x_pred = x

    # Splitting the in- and out-of-bag samples
    ib_idxs, oob_idxs = get_bootstrap_idxs(x, bag_size)
    x_ib, y_ib = x[ib_idxs], y[ib_idxs]

    # Fitting and predicting the model
    model.fit(x_ib, y_ib, **model_kwargs)
    y_pred = model.predict(x_pred)

    return y_pred

def bootstrap_model(x, y, bag_size=0.5, model=Lowess(), x_pred=None, num_runs=1000, **model_kwargs):
    # Creating the ensemble predictions
    preds = []

    for bootstrap_run in track(range(num_runs)):
        y_pred = run_model(x, y, bag_size, model=model, x_pred=x_pred, **model_kwargs)
        preds += [y_pred]

    # Wrangling into a dataframe
    df_bootstrap = pd.DataFrame(preds, columns=x).T

    df_bootstrap.index.name = 'x'
    df_bootstrap.columns.name = 'bootstrap_run'

    return df_bootstrap

# Cell
def get_confidence_interval(df_bootstrap, conf_pct=0.95):
    conf_margin = (1 - conf_pct)/2
    df_conf_intvl = pd.DataFrame(columns=['min', 'max'], index=df_bootstrap.index)

    df_conf_intvl['min'] = df_bootstrap.quantile(conf_margin, axis=1)
    df_conf_intvl['max'] = df_bootstrap.quantile(1-conf_margin, axis=1)

    return df_conf_intvl

# Cell
def pred_to_quantile_loss(y, y_pred, q=0.5, weights=None):
    residuals = y - y_pred

    if weights is not None:
        residuals = weights*residuals

    loss = np.array([q*residuals, (q-1)*residuals]).max(axis=0).mean()

    return loss

def calc_quant_reg_loss(x0, x, y, q, weights=None):
    if weights is None:
        weights = np.ones(len(x))

    quantile_pred = x0[0] + x0[1]*x
    loss = pred_to_quantile_loss(y, quantile_pred, q, weights)

    return loss

calc_quant_reg_betas = lambda x, y, q=0.5, x0=np.zeros(2), weights=None, method='nelder-mead': minimize(calc_quant_reg_loss, x0, method=method, args=(x, y, q, weights)).x

# Cell
def quantile_model(x, y, model=Lowess(calc_quant_reg_betas),
                   x_pred=None, qs=np.linspace(0.1, 0.9, 9), **model_kwargs):

    if x_pred is None:
        x_pred = np.sort(np.unique(x))

    q_to_preds = dict()

    for q in track(qs):
        model.fit(x, y, q=q, **model_kwargs)
        q_to_preds[q] = model.predict(x_pred)

    df_quantiles = pd.DataFrame(q_to_preds, index=x_pred)

    df_quantiles.index.name = 'x'
    df_quantiles.columns.name = 'quantiles'

    return df_quantiles

# Cell
def calc_timedelta_dists(dates, central_date, threshold_value=24, threshold_units='W'):
    timedeltas = pd.to_datetime(dates, utc=True) - pd.to_datetime(central_date, utc=True)
    timedelta_dists = timedeltas/pd.Timedelta(value=threshold_value, unit=threshold_units)

    return timedelta_dists

# Cell
def construct_dt_weights(dt_idx, reg_dates, threshold_value=52, threshold_units='W'):
    dt_to_weights = dict()

    for reg_date in reg_dates:
        dt_to_weights[reg_date] = pd.Series(calc_timedelta_dists(dt_idx, reg_date, threshold_value=threshold_value, threshold_units=threshold_units)).pipe(dist_to_weights).values

    return dt_to_weights

# Cell
def fit_external_weighted_ensemble(x, y, ensemble_member_to_weights, **fit_kwargs):
    ensemble_member_to_models = dict()

    for ensemble_member, ensemble_weights in track(ensemble_member_to_weights.items()):
        ensemble_member_to_models[ensemble_member] = Lowess()
        ensemble_member_to_models[ensemble_member].fit(x, y, external_weights=ensemble_weights, **fit_kwargs)

    return ensemble_member_to_models

def get_ensemble_preds(ensemble_member_to_model, x_pred=np.linspace(8, 60, 53)):
    ensemble_member_to_preds = dict()

    for ensemble_member in ensemble_member_to_model.keys():
        ensemble_member_to_preds[ensemble_member] = ensemble_member_to_model[ensemble_member].predict(x_pred)

    return ensemble_member_to_preds

# Cell
class SmoothDates(BaseEstimator, RegressorMixin):
    def __init__(self):
        self.fitted = False
        pass

    def fit(self, x, y, dt_idx, reg_dates, threshold_value=52, threshold_units='W', **fit_kwargs):
        self.ensemble_member_to_weights = construct_dt_weights(dt_idx, reg_dates,
                                                               threshold_value=threshold_value,
                                                               threshold_units=threshold_units)

        self.ensemble_member_to_models = fit_external_weighted_ensemble(x, y, self.ensemble_member_to_weights, **fit_kwargs)

        self.reg_dates = reg_dates
        self.fitted = True

        return

    def predict(self, x_pred=np.linspace(8, 60, 53), dt_pred=None, return_df=True):
        if dt_pred is None:
            dt_pred = self.reg_dates

        self.ensemble_member_to_preds = get_ensemble_preds(self.ensemble_member_to_models, x_pred=x_pred)

        self.pred_weights = np.array(list(construct_dt_weights(dt_pred, self.reg_dates).values()))
        self.pred_values = np.array(list(self.ensemble_member_to_preds.values()))

        y_pred = np.dot(self.pred_weights.T, self.pred_values)

        if return_df == True:
            df_pred = pd.DataFrame(y_pred, index=dt_pred, columns=x_pred).T
            return df_pred
        else:
            return y_pred