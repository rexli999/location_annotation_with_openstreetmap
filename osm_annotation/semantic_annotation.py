import os
import sys
from glob import glob
import pandas as pd
from shapely.geometry import shape
import fiona
from shapely.geometry.polygon import Polygon
from gps2space import geodf, dist
import geopandas as gpd
from tqdm import tqdm

"""
The SemanticAnnotator class aims to annotate location data using geofabrik database created by geofabrik_database.py. 

There are three annotation methods:
    1. annotate_single_point(lat, lon): annotate single point with semantic labels from OpenStreetMap database.
        - pro: return distances to all POI types 
        - con: time-consuming (~2 hours/query). Method 3 is recommended for batch of points. 
    2. annotate_single_shape(lat_list, lon_list): annotate single shape (e.g., bounding box, polygon) with semantic labels from OpenStreetMap database. 
        - pro: most accurate method
        - con: need a set of points define the query shape
    3. annotate_batch_points(dataframe, latitude_colname, longitude_colname): annotate a batch of points (usually centroids of places) with semantic labels from OpenStreetMap database.
        - pro: fastest method. Fit for annotating many centroids of places simultaneously. 
        - con: just return the label of the nearest POI and the distance.   
    
This script uses the geodf and dist functions from the GPS2space package (https://gps2space.readthedocs.io/en/latest/).
    
"""


class SemanticAnnotator:
    def __init__(self, database_folder_path):
        self.geofabrik_combined_folder_path = os.path.join(database_folder_path, "organized_landmarks_combined")

    def _get_shapely_poly(self, lat_list, lon_list):
        cluster_poly = Polygon([(x, y) for x, y in zip(lon_list, lat_list)])  # list of (longitude, latitude)
        return cluster_poly

    def annotate_single_point(self, lat, lon):
        """annotate single point with semantic labels from OpenStreetMap database.
        Match the nearest POI to the query point.

        Parameters:
           lat (long): latitude of the query point, in degree
           lon (long): longitude of the query point, in degree
        Returns:
           a json file with
                matched_labels: semantic label matched with the query point
                min_distance: the distance from the query point to the matched POI, in meters
                distances_to_pois: distance to other types of POIs
        """

        osm_label_list = []
        distance_list = []

        centroid = [[lon, lat]]
        df_centroid_point = pd.DataFrame(data=centroid, columns=['longitude', 'latitude'])
        cluster_centroid_point = geodf.df_to_gdf(df_centroid_point, x='longitude', y='latitude')

        # iterate through all level3 landmarks and find associated labels (lvl1, lvl2, lvl3)

        for lvl1_label in tqdm(os.listdir(self.geofabrik_combined_folder_path)):
            # print("Level 1 : "+lvl1_label)
            lvl1_path = self.geofabrik_combined_folder_path + os.sep + lvl1_label
            for lvl2_label in os.listdir(lvl1_path):
                # print("  Level 2 : "+lvl2_label)
                lvl2_path = lvl1_path + os.sep + lvl2_label
                for lvl3_label in os.listdir(lvl2_path):
                    # print("    Level 3 : "+lvl3_label)
                    lvl3_path = lvl2_path + os.sep + lvl3_label

                    finding_list_point = list(glob(os.path.join(lvl3_path, "*_point.shp")))
                    if len(finding_list_point) > 0:
                        point_shp_path = finding_list_point[0]
                        gdf_landmark = gpd.read_file(point_shp_path)

                        nearest_POI = dist.dist_to_point(cluster_centroid_point, gdf_landmark, proj=2163)
                        distance = list(nearest_POI['dist2point'])[0]
                        distance_list.append(distance)
                        osm_label_list.append("{};{};{} (point)".format(lvl1_label, lvl2_label, lvl3_label))

                    finding_list_poly = list(glob(os.path.join(lvl3_path, "*_polygon.shp")))
                    if len(finding_list_poly) > 0:
                        poly_shp_path = finding_list_poly[0]

                        gdf_landmark = gpd.read_file(poly_shp_path)
                        gdf_landmark = gdf_landmark.to_crs('epsg:2163')
                        gdf_landmark.geometry = gdf_landmark.geometry.centroid

                        nearest_POI = dist.dist_to_point(cluster_centroid_point, gdf_landmark, proj=2163)
                        distance = list(nearest_POI['dist2point'])[0]
                        distance_list.append(distance)
                        osm_label_list.append("{};{};{} (polygon)".format(lvl1_label, lvl2_label, lvl3_label))

        min_idx = distance_list.index(min(distance_list))
        min_distance = min(distance_list)
        osm_label = osm_label_list[min_idx]

        result_json = {"matched_labels": osm_label,
                       "min_distance": min_distance,
                       "distances_to_pois": dict(zip(osm_label_list, distance_list))
                       }

        return result_json

    def annotate_single_shape(self, lat_list, lon_list):
        """annotate single shape with semantic labels from OpenStreetMap database.
        The shape can be of any geometric shape that can be described with a list of latitude and longitude.
            e.g., a bound box, a polygon
        Match with the label of the point POI (OSM POI represented by a point) within the query shape
            and with the label of the polygon POI (OSM POI represented by a polygon) intersected with the query shape.

        Parameters:
           lat_list (long): a list of latitudes of the query shape, in degree
           lon_list (long): a list of longitudes of the query shape, in degree
        Returns:
           a json file with
                matched_labels: semantic labels matched with the query shape
                point_labels: semantic labels of point POI matched with the query shape
                poly_labels: semantic labels of polygon POI matched with the query shape
                matched_geometries: geometries of POIs matched with the query shape
        """
        if len(lat_list) == 0 or len(lon_list) == 0:
            return

        cluster_poly = self._get_shapely_poly(lat_list, lon_list)

        point_label_list = []
        poly_label_list = []
        geo_list = []

        # iterate through all level3 landmarks and find associated labels (lvl1, lvl2, lvl3)

        for lvl1_label in tqdm(os.listdir(self.geofabrik_combined_folder_path)):
            # print("Level 1 : "+lvl1_label)
            lvl1_path = self.geofabrik_combined_folder_path + os.sep + lvl1_label
            for lvl2_label in os.listdir(lvl1_path):
                # print("  Level 2 : "+lvl2_label)
                lvl2_path = lvl1_path + os.sep + lvl2_label
                for lvl3_label in os.listdir(lvl2_path):
                    # print("    Level 3 : "+lvl3_label)
                    lvl3_path = lvl2_path + os.sep + lvl3_label

                    finding_list_point = list(glob(os.path.join(lvl3_path, "*_point.shp")))
                    if len(finding_list_point) > 0:
                        point_shp_path = finding_list_point[0]
                        gdf_landmark_point = fiona.open(point_shp_path)

                        for next_shp in gdf_landmark_point:
                            geo = shape(next_shp['geometry'])
                            if cluster_poly.contains(geo):  # polygon contains a point landmark
                                point_label_list.append("{};{};{} (point)".format(lvl1_label, lvl2_label, lvl3_label))
                                geo_list.append(geo)
                                break

                    finding_list_poly = list(glob(os.path.join(lvl3_path, "*_polygon.shp")))
                    if len(finding_list_poly) > 0:
                        poly_shp_path = finding_list_poly[0]
                        gdf_landmark_poly = fiona.open(poly_shp_path)

                        for next_shp in gdf_landmark_poly:
                            geo = shape(next_shp['geometry'])
                            if cluster_poly.intersects(geo):  # polygon intersects a polygon landmark
                                poly_label_list.append("{};{};{} (polygon)".format(lvl1_label, lvl2_label, lvl3_label))
                                geo_list.append(geo)
                                break

        result_json = {"matched_labels": point_label_list + list(set(poly_label_list) - set(point_label_list)),
                       "point_labels": point_label_list,
                       "poly_labels": poly_label_list,
                       "matched_geometries": geo_list}

        return result_json

    def annotate_batch_points(self, dataframe, latitude_colname, longitude_colname):
        """annotate a batch of points (usually centroids of places) with semantic labels from OpenStreetMap database.
        The batch of points should be stored in a panda dataframe with columns of latitude and longitude.
        Match the nearest POI to each query point.

        Parameters:
            a dataframe with
                lat_list (long): a list of latitudes of the query shape, in degree
                lon_list (long): a list of longitudes of the query shape, in degree
        Returns:
           a dataframe with
                matched_labels: semantic labels matched with the query points
                min_distance: the distance from the query point to the matched POI, in meters
        """
        if dataframe.shape[0] == 0:
            return

        cluster_centroid_point_p = geodf.df_to_gdf(dataframe, x=longitude_colname, y=latitude_colname)
        cluster_centroid_point_p = cluster_centroid_point_p.to_crs('epsg:2163')
        cluster_centroid_point_p.reset_index(inplace=True, drop=True)

        dist2point_df = pd.DataFrame()

        # iterate through all level3 landmarks and find associated labels (lvl1, lvl2, lvl3)

        for lvl1_label in tqdm(os.listdir(self.geofabrik_combined_folder_path)):
            # print("Level 1 : " + lvl1_label)
            lvl1_path = self.geofabrik_combined_folder_path + os.sep + lvl1_label
            for lvl2_label in os.listdir(lvl1_path):
                # print("  Level 2 : " + lvl2_label)
                lvl2_path = lvl1_path + os.sep + lvl2_label
                for lvl3_label in os.listdir(lvl2_path):
                    # print("    Level 3 : " + lvl3_label)
                    lvl3_path = lvl2_path + os.sep + lvl3_label

                    finding_list_point = list(glob(os.path.join(lvl3_path, "*_point.shp")))
                    if len(finding_list_point) > 0:
                        point_shp_path = finding_list_point[0]

                        gdf_landmark = gpd.read_file(point_shp_path)
                        nearest_POI = dist.dist_to_point(cluster_centroid_point_p, gdf_landmark, proj=2163)
                        dist2point_df["{};{};{} (point)".format(lvl1_label, lvl2_label, lvl3_label)] = \
                            nearest_POI["dist2point"]

                    finding_list_poly = list(glob(os.path.join(lvl3_path, "*_polygon.shp")))
                    if len(finding_list_poly) > 0:
                        poly_shp_path = finding_list_poly[0]

                        gdf_landmark = gpd.read_file(poly_shp_path)
                        gdf_landmark = gdf_landmark.to_crs('epsg:2163')
                        gdf_landmark.geometry = gdf_landmark.geometry.centroid

                        nearest_POI = dist.dist_to_point(cluster_centroid_point_p, gdf_landmark, proj=2163)
                        dist2point_df["{};{};{} (polygon)".format(lvl1_label, lvl2_label, lvl3_label)] = \
                            nearest_POI["dist2point"]

        nearest_POI_list = dist2point_df.idxmin(axis=1)
        nearest_POI_dist_list = dist2point_df.min(axis=1)
        dataframe["matched_labels"] = nearest_POI_list
        dataframe["min_distance"] = nearest_POI_dist_list

        return dataframe


if __name__ == "__main__":
    geofabrik_combined_folder_path = sys.argv[1]
    semanticAnnotator = SemanticAnnotator(geofabrik_combined_folder_path)
    semanticAnnotator.annotate_single_shape()
    semanticAnnotator.annotate_batch_points()
    semanticAnnotator.annotate_single_point()
