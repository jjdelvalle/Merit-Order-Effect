# AUTOGENERATED! DO NOT EDIT! File to edit: dev/02-eda.ipynb (unless otherwise specified).

__all__ = ['load_EI_df', 'load_DE_df', 'clean_df_for_plot', 'rgb_2_plt_tuple', 'convert_fuel_colour_dict_to_plt_tuple',
           'hide_spines', 'stacked_fuel_plot']

# Cell
import pandas as pd

import seaborn as sns
import matplotlib.pyplot as plt
import matplotlib.transforms as mtf

# Cell
def load_EI_df(EI_fp):
    """Loads the electric insights data and returns a DataFrame"""
    df = pd.read_csv(EI_fp)

    df['local_datetime'] = pd.to_datetime(df['local_datetime'], utc=True)
    df = df.set_index('local_datetime')

    return df

# Cell
def load_DE_df(EC_fp, ENTSOE_fp):
    """Loads the energy-charts and ENTSOE data and returns a DataFrame"""
    # Energy-Charts
    df_DE = pd.read_csv(EC_fp)

    df_DE['local_datetime'] = pd.to_datetime(df_DE['local_datetime'], utc=True)
    df_DE = df_DE.set_index('local_datetime')

    # ENTSOE
    df_ENTSOE = pd.read_csv(ENTSOE_fp)

    df_ENTSOE['local_datetime'] = pd.to_datetime(df_ENTSOE['local_datetime'], utc=True)
    df_ENTSOE = df_ENTSOE.set_index('local_datetime')

    # Combining data
    df_DE['demand'] = df_DE.sum(axis=1)

    s_price = df_ENTSOE['DE_price']
    df_DE['price'] = s_price[~s_price.index.duplicated(keep='first')]

    return df_DE

# Cell
def clean_df_for_plot(df, freq='7D'):
    """Cleans the electric insights dataframe for plotting"""
    fuel_order = ['Imports & Storage', 'nuclear', 'biomass', 'gas', 'coal', 'hydro', 'wind', 'solar']
    interconnectors = ['french', 'irish', 'dutch', 'belgian', 'ireland', 'northern_ireland']

    df = (df
          .copy()
          .assign(imports_storage=df[interconnectors+['pumped_storage']].sum(axis=1))
          .rename(columns={'imports_storage':'Imports & Storage'})
          .drop(columns=interconnectors+['demand', 'pumped_storage'])
          [fuel_order]
         )

    df_resampled = df.astype('float').resample(freq).mean()
    return df_resampled

# Cell
def rgb_2_plt_tuple(rgb_tuple):
    """converts a standard rgb set from a 0-255 range to 0-1"""
    plt_tuple = tuple([x/255 for x in rgb_tuple])
    return plt_tuple

def convert_fuel_colour_dict_to_plt_tuple(fuel_colour_dict_rgb):
    """Converts a dictionary of fuel colours to matplotlib colour values"""
    fuel_colour_dict_plt = fuel_colour_dict_rgb.copy()

    fuel_colour_dict_plt = {
        fuel: rgb_2_plt_tuple(rgb_tuple)
        for fuel, rgb_tuple
        in fuel_colour_dict_plt.items()
    }

    return fuel_colour_dict_plt

# Cell
def hide_spines(ax, positions=["top", "right"]):
    """
    Pass a matplotlib axis and list of positions with spines to be removed

    Parameters:
        ax:          Matplotlib axis object
        positions:   Python list e.g. ['top', 'bottom']
    """
    assert isinstance(positions, list), "Position must be passed as a list "

    for position in positions:
        ax.spines[position].set_visible(False)

def stacked_fuel_plot(df, fuel_colour_dict, ax=None, save_path=None, dpi=150):
    """Plots the electric insights fuel data as a stacked area graph"""
    df = df[fuel_colour_dict.keys()]

    if ax == None:
        fig = plt.figure(figsize=(10, 5), dpi=dpi)
        ax = plt.subplot()

    ax.stackplot(df.index.values, df.values.T, labels=df.columns.str.capitalize(), linewidth=0.25, edgecolor='white', colors=list(fuel_colour_dict.values()))

    plt.rcParams['axes.ymargin'] = 0
    ax.spines['bottom'].set_position('zero')
    hide_spines(ax)

    ax.set_xlim(df.index.min(), df.index.max())
    ax.legend(ncol=4, bbox_to_anchor=(0.85, 1.15), frameon=False)
    ax.set_ylabel('Generation (GW)')

    if save_path:
        fig.savefig(save_path)

    return ax