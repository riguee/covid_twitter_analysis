import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import geopandas as gpd

if os.environ.get("DATA_PATH"):
    DATA_PATH = os.environ["DATA_PATH"]
else:
    DATA_PATH = f"covid_emo_top_loc/"

if os.environ.get("GRAPH_PATH"):
    GRAPH_PATH = os.environ["GRAPH_PATH"]
else:
    GRAPH_PATH = "graphs/"

PROJECTION_DF = {
    "GB": 27700,
    "ES": 2062,
    "IT": 6875,
    "DE": 3068,
    "FR": 2192,
    "NL": 28992,
    "EU": 5643,
}


class Country:
    def __init__(self, country_code):

        # open dgurba shapefile which incudes the LAU boundaries
        self.URBA = gpd.read_file(f"{DATA_PATH}DGURBA/DGURBA-2020-01M-SH.shp")
        self.pop_grid = gpd.read_file(
            f"{DATA_PATH}JRC_GRID_2018/JRC_POPULATION_2018.shp"
        )
        self.country_code = country_code

        # get relevant data
        self.URBA = (
            self.URBA
            if self.country_code == "EU"
            else self.URBA.loc[self.URBA["CNTR_CODE"] == self.country_code]
        )
        self.pop_grid = (
            self.pop_grid
            if self.country_code == "EU"
            else self.pop_grid.loc[self.pop_grid["CNTR_ID"] == self.country_code]
        )

        # reproject data according to the relevant crs
        self.URBA = self.URBA.to_crs(epsg=PROJECTION_DF[self.country_code])
        self.pop_grid = self.pop_grid.to_crs(epsg=PROJECTION_DF[self.country_code])

    def compute_population_per_lau(self):
        # overlay LAUs and the population grid
        urba_grid_overlay = gpd.overlay(self.URBA, self.pop_grid)
        # take the area of that
        urba_grid_overlay_area = urba_grid_overlay.area
        urba_grid_overlay["overlay_area"] = urba_grid_overlay_area
        # look at the area of each population grid square
        self.pop_grid["area"] = self.pop_grid.area
        # merge the overlay areas with the population df to get the population information
        urba_grid_overlay_areas = urba_grid_overlay.merge(
            self.pop_grid[["OBJECTID", "TOT_P_2018", "area"]],
            left_on="OBJECTID_2",
            right_on="OBJECTID",
            how="left",
        )
        # look at the overall grid square area matched within LAUS
        # we do that as some squares might be outside of the any LAU,
        # and then we must recompute the fraction of the population to account for that
        overall_grid_areas = (
            urba_grid_overlay_areas[["OBJECTID", "overlay_area", "area"]]
            .groupby("OBJECTID")
            .agg({"overlay_area": "sum"})
            .rename(columns={"overlay_area": "total_square_area"})
        )
        urba_grid_overlay_areas = urba_grid_overlay_areas.merge(
            overall_grid_areas, left_on="OBJECTID", right_index=True, how="left"
        )
        # compute the fraction of the population in the LAU as the ratio of the overlapping grid square in the LAU,
        # against the area of the square overlapping any LAU
        urba_grid_overlay_areas["fraction"] = (
            urba_grid_overlay_areas["overlay_area"]
            / urba_grid_overlay_areas["total_square_area"]
        )
        urba_grid_overlay_areas["fraction_pop"] = (
            urba_grid_overlay_areas["TOT_P_2018_y"]
            * urba_grid_overlay_areas["fraction"]
        )
        # group that by LAU to obtain the final LAU population
        # add this to the URBA dataframe
        self.weighted_pop_lau = (
            urba_grid_overlay_areas[["OBJECTID_1", "fraction_pop"]]
            .groupby("OBJECTID_1")
            .sum()
        )
        self.URBA = self.URBA.merge(
            self.weighted_pop_lau, left_on="OBJECTID", right_index=True
        )

    def print_summary_DGURBA(self, savefig=False):
        fig, ax = plt.subplots(figsize=(10, 6))
        c1, c2 = ("tomato", "forestgreen")
        width = 0.4

        ax = self.DGURBA_summary["population", "sum"].plot.bar(
            color=c1, width=width, position=1, rot=0
        )
        ax2 = ax.twinx()
        self.DGURBA_summary["area_pct", "sum"].plot.bar(
            color=c2, ax=ax2, width=width, position=0, rot=0
        )
        plt.xlim([-1, 3])

        ax.set_ylabel("population sum")
        ax2.set_ylabel("sum of LAU areas")
        ax.yaxis.label.set_color(c1)
        ax2.yaxis.label.set_color(c2)

        ax.set_title("Population and land area by degree of urbanisation")

        plt.tight_layout()
        if savefig:
            plt.savefig(f"{GRAPH_PATH}population_land_lau.png")
        plt.show()

    def get_summary_DGURBA(self, plot=True):
        tmp_urba = self.URBA.copy()
        tmp_urba["area"] = tmp_urba.area
        tmp_urba["area_pct"] = tmp_urba["area"] / tmp_urba["area"].sum()
        aggregations = {
            "population": ["sum", "mean", "idxmax", "idxmin"],
            "area_pct": ["sum", "mean", "idxmax", "idxmin"],
        }
        self.DGURBA_summary = tmp_urba.groupby("DGURBA").agg(aggregations)
        if plot:
            self.print_summary_DGURBA()

