import os
import sys
import time
from glob import glob
import requests
import zipfile
import shutil
from tqdm import tqdm
import pkg_resources

import pandas as pd
import geopandas as gpd
import shapely
import warnings

warnings.filterwarnings("ignore")

"""
global variables
"""
# user settings
update_shapefiles = False # if True, redownload shapefiles from Geofabrik to update the current databases.
label_map_path = pkg_resources.resource_filename('osm_annotation', 'label_map/osm_label_hierarchy.csv')
# label_map_path = os.path.join(os.path.dirname(__file__), 'label_map/osm_label_hierarchy.csv')
state_string = "alabama, alaska, arizona, arkansas, norcal, socal, colorado, connecticut, delaware, district of columbia, florida, georgia, hawaii, idaho, illinois, indiana, iowa, kansas, kentucky, louisiana, maine, maryland, massachusetts, michigan, minnesota, mississippi, missouri, montana, nebraska, nevada, new hampshire, new jersey, new mexico, new york, north carolina, north dakota, ohio, oklahoma, oregon, pennsylvania, puerto rico, rhode island, south carolina, south dakota, tennessee, texas, united states virgin islands, utah, vermont, virginia, washington, west virginia, wisconsin, wyoming"
state_list = state_string.split(", ")

# OSM related
base_url = "http://download.geofabrik.de/north-america/us/"
layers = ["buildings", "landuse", "natural", "places", "pofw", "pois", "railways", "roads", "traffic", "transport",
          "water", "waterways"]


def _create_folder(p):
    if not os.path.exists(p):
        os.makedirs(p)


def _get_shp_file_link(state):
    if state == 'united states virgin islands':
        state_name = "us-virgin-islands"
    elif state == 'norcal' or state == 'socal':
        state_name = "california/" + state
    else:
        state_name = state.replace(" ", "-")
    return base_url + state_name + "-latest-free.shp.zip"


def _download_state_zipfile(download_folder_path, state, url):
    r = requests.get(url, allow_redirects=True)
    save_path = os.path.join(download_folder_path, state + '.shp.zip')
    open(save_path, 'wb').write(r.content)
    return save_path


def _unzip_file(zipfile_path, zip_to_path):
    with zipfile.ZipFile(zipfile_path, 'r') as zip_ref:
        zip_ref.extractall(zip_to_path)


def _download_and_unzip(download_folder_path, unzipped_folder_path):
    """download and unzip Geofabrik shapefiles to the designated folder.

    Parameters:
       global variables
    Returns:
       None
    """
    start = time.time()
    print("======================================================================================================")
    print("Start (this process may take about 20 minutes)")
    print("   1. downloading Geofabrik data for all states to {}".format(download_folder_path))
    print("   2. unzipping Geofabrik data for all states to {}".format(unzipped_folder_path))

    _create_folder(download_folder_path)
    _create_folder(unzipped_folder_path)
    for state in state_list:
        print(state)
        # update
        zip_to_path = os.path.join(unzipped_folder_path, state)

        if os.path.exists(zip_to_path):
            print("    " + "skip because unzipped file exists")
            continue

        # download
        url = _get_shp_file_link(state)
        download_save_path = _download_state_zipfile(download_folder_path, state, url)
        print("    " + url)
        print("    " + "Downloaded to : " + download_save_path)

        # unzip
        zipfile_path = os.path.join(download_folder_path, state + '.shp.zip')
        _unzip_file(zipfile_path, zip_to_path)
        print("    " + "Unzipped to : " + zip_to_path)

    end = time.time()

    print("End:  runtime is {} min".format((end - start) / 60))
    print("")
    return


def _clean_line(line):
    line = line.lower()
    line = line.replace(" ", "_")
    line = line.replace("s,", ",")
    return line


def _clean_label_map():
    clean_label_map_path = label_map_path.split(".csv")[0] + "_clean.csv"

    with open(label_map_path) as inputF:
        Lines = inputF.readlines()
        with open(clean_label_map_path, 'w') as outputF:
            for line in Lines[1:]:  # skip head line
                line = _clean_line(line)
                outputF.write(line)
    return clean_label_map_path


def _parse_label_map():
    """parse the label hierarchy map.

    Parameters:
       global variables
    Returns:
       map_dict
    """

    print("======================================================================================================")
    print("Start parsing the label hierarchy map")

    # first run "clean_csv_map" and use the label map ended with "_clean.csv".
    clean_label_map_path = _clean_label_map()

    # convert csv map to json map
    map_dict = {"unique_list": [], "map": {}}

    with open(clean_label_map_path) as fp:
        Lines = fp.readlines()
        for line in Lines:  # skip head line
            line_list = line.split(",")
            label_1st = line_list[0]
            label_2nd = line_list[1]
            label_3rd = line_list[2]
            if len(label_1st) > 0:
                level1 = label_1st
                map_dict['map'][level1] = dict()
                map_dict['unique_list'].append(label_1st)
            if len(label_2nd) > 0:
                level2 = label_2nd
                map_dict['map'][level1][level2] = dict()
                map_dict['unique_list'].append(label_2nd)
            if len(label_3rd) > 0:
                line_list_lvl3 = [x for x in line_list if (len(x) > 0) and (x != '\n')]
                map_dict['map'][level1][level2][label_3rd] = line_list_lvl3[1:]
                map_dict['unique_list'] += line_list_lvl3

    return map_dict


def _extract_all_landmarks_from_shapefile(label_map, organized_data_folder_path, shpfile_df_single_tag,
                                          shpfile_df_multi_tag, column_to_check, state, category, layer, shpfile_num):
    included_num = 0
    for lvl1_label in label_map:  # from top level to bottom level
        #     print("Level 1 : "+lvl1_label)
        lvl1_path = organized_data_folder_path + os.sep + lvl1_label
        _create_folder(lvl1_path)
        for lvl2_label in label_map[lvl1_label]:
            #         print("  Level 2 : "+lvl2_label)
            lvl2_path = lvl1_path + os.sep + lvl2_label
            label_map_lvl2 = label_map[lvl1_label][lvl2_label]
            _create_folder(lvl2_path)
            for lvl3_label in label_map[lvl1_label][lvl2_label]:
                #             print("    Level 3 : "+lvl3_label)
                lvl3_path = lvl2_path + os.sep + lvl3_label
                lvl3_file_name = "_".join([lvl3_label, state, layer, shpfile_num, category + ".shp"])
                lvl3_file_path = os.path.join(lvl3_path, lvl3_file_name)

                if os.path.exists(lvl3_file_path):
                    continue
                _create_folder(lvl3_path)
                synonyms = label_map_lvl2[lvl3_label]
                labels = [x for x in synonyms]
                labels.insert(0, lvl3_label)

                df_label = pd.DataFrame()
                for label in labels:
                    shpfile_df_single_tag_label = shpfile_df_single_tag[shpfile_df_single_tag[column_to_check] == label]
                    shpfile_df_multi_tag_label = shpfile_df_multi_tag[
                        shpfile_df_multi_tag[column_to_check].str.contains(label)]
                    df_label = df_label.append(shpfile_df_single_tag_label)
                    df_label = df_label.append(shpfile_df_multi_tag_label)

                # save extraction to shapefile
                if df_label.shape[0] > 0:
                    df_label.to_file(lvl3_file_path)
                    included_num += df_label.shape[0]
    return included_num


def _clean_tag_column(tag_series):
    cleaned_series = tag_series.str.lower()
    cleaned_series = cleaned_series.str.replace(" ", "_", case=False)
    cleaned_series = pd.Series([x[:-1] if x.endswith('s') else x for x in cleaned_series])

    return cleaned_series


def _get_poi_inclusion_stats(label_count_dict):
    print("#POI included in local database / # POI labeled with semantics by OSM")
    for layer in label_count_dict:
        print(f"  {layer} : {round(label_count_dict[layer]['included'] / label_count_dict[layer]['labeled'], 3)}")
    return


def _determine_state_in_last_run(organized_data_folder_path):
    processed_state_set = set()
    for osm_file_path in glob(os.path.join(organized_data_folder_path, "**", "*_1_*.shp"), recursive=True):
        for state in state_list:
            if state in osm_file_path.split(os.sep)[-1]:
                processed_state_set.add(state)

    print("processed state : {}".format(processed_state_set))
    if len(processed_state_set) == 0:
        return state_list[0]
    else:
        idx_in_state_list = [state_list.index(x) for x in list(processed_state_set)]
        idx_max = max(idx_in_state_list)
        return state_list[idx_max]


def _reorganize_shapefiles(map_dict, organized_data_folder_path, unzipped_folder_path):
    """reorganize downloaded shapefiles to build a local database of Geofabrik shapefiles in designated folder path.
    The file system follows the structure in the user-specified label hierarchy.
    The downloaded shapefiles has the structure of state - point/polygon - layer - label.
    We extract POIs from each state and then put them into the file system following the structure of the user-specified label map.

    Parameters:
       map_dict: the parsed label map
    Returns:
       None
    """

    print("======================================================================================================")
    print("Start reorganizing shapefiles into label map structure ")
    print(
        "(The whole process may takes several hours. You may stop at any time and continue later by setting update_shapefiles = False)")

    start_time = time.time()

    label_map = map_dict['map']
    _create_folder(organized_data_folder_path)

    label_count_dict = dict()
    for layer in layers:
        label_count_dict[layer] = {"none": 0, "labeled": 0,
                                   "included": 0}  # statistics of OSM POI labeling and inclusion in the label map.

    # continue with the last state that the program stops at in the last run
    state_last_run = _determine_state_in_last_run(organized_data_folder_path)

    start = 0
    for state in tqdm(state_list):
        print("")
        print(state)

        if state == state_last_run:
            start = 1
        if start == 0:
            print("Already processed")
            continue

        # start_state = time.time()
        state_folder_path = os.path.join(unzipped_folder_path, state)
        for category in ["point", "polygon"]:
            # print("  " + category)
            if category == "point":
                suffix = "_free_*.shp"
                filename_suffix = "_point"
            elif category == "polygon":
                suffix = "_a_free_*.shp"
                filename_suffix = "_polygon"
            else:
                pass

            for layer in layers:
                # print("    " + layer)
                shapefile_pattern = os.path.join(state_folder_path, "gis_osm_" + layer + suffix)
                shapefile_finding_list = list(glob(shapefile_pattern))
                # if len(shapefile_finding_list) > 1:
                #     print("{} shapefiles found for {} for state {}".format(len(shapefile_finding_list), layer, state))

                for p_shapefile in shapefile_finding_list:
                    shpfile_df = gpd.read_file(p_shapefile)
                    label_count_dict[layer]["none"] += shpfile_df.shape[0]
                    column_to_check = ["fclass", "type"]
                    column_to_check = list(set(shpfile_df.columns).intersection(column_to_check))
                    if len(column_to_check) > 1:
                        if len(shpfile_df['fclass'].unique()) > len(shpfile_df['type'].unique()):
                            column_to_check = "fclass"
                        else:
                            column_to_check = "type"
                    else:
                        column_to_check = column_to_check[0]
                    # print("      column to check : " + column_to_check)
                    #                 column_to_check = list(set(shpfile_df.columns).intersection(column_to_check))
                    shpfile_num = p_shapefile.split("_free_")[1].strip(".shp")

                    # clean label columns: lower case, replace space with underscore, remove ending s, split by ";"
                    shpfile_df["tag_col_type"] = ["none" if x is None else "str" for x in shpfile_df[column_to_check]]
                    shpfile_df = shpfile_df[shpfile_df["tag_col_type"] != "none"]
                    label_count_dict[layer]["labeled"] += shpfile_df.shape[0]
                    shpfile_df.reset_index(inplace=True, drop=True)
                    shpfile_df[column_to_check] = _clean_tag_column(shpfile_df[column_to_check])
                    shpfile_df[column_to_check] = shpfile_df[column_to_check].astype(str)
                    shpfile_df_single_tag = shpfile_df[~shpfile_df[column_to_check].str.contains(";")]
                    shpfile_df_single_tag.reset_index(inplace=True, drop=True)
                    shpfile_df_multi_tag = shpfile_df[shpfile_df[column_to_check].str.contains(";")]
                    shpfile_df_multi_tag.reset_index(inplace=True, drop=True)

                    included_num = _extract_all_landmarks_from_shapefile(label_map, organized_data_folder_path,
                                                                         shpfile_df_single_tag, shpfile_df_multi_tag,
                                                                         column_to_check, state, category, layer,
                                                                         shpfile_num)
                    label_count_dict[layer]["included"] += included_num
        # end_state = time.time()
        # print(f"Runtime for {state} is {end_state - start_state}")

    if state_last_run == state_list[0]:  # generate the stats only when reprocess all states
        _get_poi_inclusion_stats(label_count_dict)

    end_time = time.time()
    print("End:  all state shapefiles have been extracted and reorganized.")
    print("Total runtime is {} min".format((end_time - start_time) / 60))
    print("")
    return


def _rearrange_shapefiles(organized_data_folder_path, combined_data_folder_path):
    """combine files for states and layers.

    Parameters:
       global variables
    Returns:
       None
    """

    print("======================================================================================================")
    print("Start rearrange shapefiles (last step, this process may take about 3 hours)")
    start_time = time.time()
    start = 0
    for lvl1 in tqdm(os.listdir(organized_data_folder_path)):
        print(lvl1)
        lvl1_path = os.path.join(organized_data_folder_path, lvl1)
        for lvl2 in os.listdir(lvl1_path):
            print("  " + lvl2)
            lvl2_path = os.path.join(lvl1_path, lvl2)
            for lvl3 in os.listdir(lvl2_path):
                print("    " + lvl3)
                # if lvl3 == "house":
                #     start = 1
                # if start == 0:
                #     continue

                lvl3_path = os.path.join(lvl2_path, lvl3)
                df_point = pd.DataFrame()
                df_polygon = pd.DataFrame()
                df_folder_path = os.path.join(combined_data_folder_path, lvl1, lvl2, lvl3)
                _create_folder(df_folder_path)
                df_point_path = os.path.join(df_folder_path, lvl3 + "_point.shp")
                df_line_path = os.path.join(df_folder_path, lvl3 + "_line.shp")
                df_polygon_path = os.path.join(df_folder_path, lvl3 + "_polygon.shp")

                if not os.path.exists(df_point_path):
                    for target_file in glob(os.path.join(lvl3_path, "*point.shp")):
                        shpfile_df = gpd.read_file(target_file)
                        df_point = df_point.append(shpfile_df)
                    if df_point.shape[0] > 0:
                        df_point['geo_type'] = [type(x) for x in df_point.geometry]
                        df_line = df_point[df_point['geo_type'] == shapely.geometry.linestring.LineString]
                        if df_line.shape[0] > 0:
                            df_point = df_point[df_point['geo_type'] == shapely.geometry.point.Point]
                            df_line.reset_index(inplace=True, drop=True)
                            df_point.reset_index(inplace=True, drop=True)
                            df_point = df_point.drop('geo_type', 1)
                            df_line = df_line.drop('geo_type', 1)
                            if df_point.shape[0] > 0:
                                df_point.to_file(df_point_path)
                            df_line.to_file(df_line_path)
                        else:
                            df_point = df_point.drop('geo_type', 1)
                            df_point.reset_index(inplace=True, drop=True)
                            df_point.to_file(df_point_path)

                if not os.path.exists(df_polygon_path):
                    for target_file in glob(os.path.join(lvl3_path, "*polygon.shp")):
                        shpfile_df = gpd.read_file(target_file)
                        df_polygon = df_polygon.append(shpfile_df)
                    if df_polygon.shape[0] > 0:
                        df_polygon.reset_index(inplace=True, drop=True)
                        df_polygon.to_file(df_polygon_path)

    end_time = time.time()
    print("Runtime of the program is {} min".format((end_time - start_time) / 60))


def build(database_folder_path):
    """builds a local database of Geofabrik shapefiles in designated folder path.
    The file system follows the structure in the user-specified label hierarchy.

    Parameters:
       database_folder_path (file path): the local file path to store Geofabrik shapefiles
    Returns:
       None
    """

    download_folder_path = os.path.join(database_folder_path, "download")
    unzipped_folder_path = os.path.join(database_folder_path, "unzipped")
    organized_data_folder_path = os.path.join(database_folder_path, "organized_landmarks")
    combined_data_folder_path = os.path.join(database_folder_path, "organized_landmarks_combined")

    if update_shapefiles:  # delete all databases
        if os.path.exists(download_folder_path):
            shutil.rmtree(download_folder_path)
        if os.path.exists(unzipped_folder_path):
            shutil.rmtree(unzipped_folder_path)
        if os.path.exists(organized_data_folder_path):
            shutil.rmtree(organized_data_folder_path)
        if os.path.exists(combined_data_folder_path):
            shutil.rmtree(combined_data_folder_path)

    _download_and_unzip(download_folder_path, unzipped_folder_path)
    map_dict = _parse_label_map()
    _reorganize_shapefiles(map_dict, organized_data_folder_path, unzipped_folder_path)
    _rearrange_shapefiles(organized_data_folder_path, combined_data_folder_path)

    return


if __name__ == "__main__":
    database_folder_path = sys.argv[1]
    build(database_folder_path)
