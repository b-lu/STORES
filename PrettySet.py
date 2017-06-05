# Identify the overlapping polygons and produce a pretty set according to water-rock ratio.
# Attach each dam to its reservoir.
# Check 1 to 4 before running the script.
# Output: RESDAM_1234_FC, RESDAM_1234.kmz

import arcpy
import glob
import re
import os
import datetime as dt

# Set working directory and geodatabase
directory = r"D:\SA" # Check 1
geodatabase = "SA_PHSites.gdb" # Check 2
arcpy.env.workspace = os.path.join(directory, geodatabase)
arcpy.env.addOutputsToMap = False
arcpy.env.parallelProcessingFactor = "75%"
arcpy.env.overwriteOutput = True
os.chdir(directory)

# Set input datasets: Lists of reservoir and dam feature classes
resfc = arcpy.ListFeatureClasses("RES_*") # Check 3
damfc = arcpy.ListFeatureClasses("DAM_*") # Check 4
print "Number of RES_: ", len(resfc)
print "Number of DAM_: ", len(damfc)

# Check if resfc, damfc equal and matched
residx = [int(e.split("_")[-1]) for e in resfc]
damidx = [int(e.split("_")[-1]) for e in damfc]
for r in residx:
    if r not in damidx:
        print "Check DAM_" + str(r)
for d in damidx:
    if d not in residx:
        print "Check RES_" + str(d)

assert len(resfc)==len(damfc), "Find the missing data."


def removal():
    
    rmvl = []
    for i in range(len(resfc)-1):
        if i in rmvl:
            continue
        for j in range(i+1, len(resfc)):
            if j in rmvl:
                continue

            # Get the latitudes and longitudes of i, j
            cursor = arcpy.SearchCursor(resfc[i])
            row = cursor.next()
            lati = float(row.getValue("LAT"))
            loni = float(row.getValue("LONG"))
            
            cursor = arcpy.SearchCursor(resfc[j])
            row = cursor.next()
            latj = float(row.getValue("LAT"))
            lonj = float(row.getValue("LONG"))

            # Accelerate the Combinations C(n, r)
            if abs(lati - latj)>0.02 or abs(loni - lonj)>0.02:
                continue

            # Calculate the intersection
            intersection = arcpy.Intersect_analysis(in_features=[resfc[i], resfc[j]], out_feature_class="ijintersect")
            cursor = arcpy.SearchCursor(intersection)
            area = [row.getValue("SHAPE_AREA") for row in cursor]

            # Compare the water-rock ratio of two polygons
            if area==[]:
                continue
            else:
                with arcpy.da.SearchCursor(resfc[i], "WATER_ROCK_RATIO") as cursor:
                    ratioi = float([r for r in cursor][0][0])
                with arcpy.da.SearchCursor(resfc[j], "WATER_ROCK_RATIO") as cursor:
                    ratioj = float([r for r in cursor][0][0])

                # Note the "worse" one in reml
                if ratioi>=ratioj:
                    rmvl.append(j)
                    print "RES_" + str(resfc[j]) + " removed"
                else:
                    rmvl.append(i)
                    print "RES_" + str(resfc[i]) + " removed"
                    break

    idxrmvl = [int(resfc[x].split("_")[1]) for x in rmvl]
    print "Remove (removal index): " + str(rmvl)
    print "Remove (RES_): " + str(idxrmvl)

    # Extract the "better" polygon
    resl = [x for x in resfc if resfc.index(x) not in rmvl]
    daml = []
    for y in resl:
        for z in damfc:
            if z.split("_")[-1]==y.split("_")[-1]:
                daml.append(z)
    assert len(resl)==len(daml)

    return resl, daml


def resdamcr8():

    # Lists of reservoirs and dams in the pretty set
    resl, daml = removal()
    
    for k in range(len(resl)):
        assert resl[k].split("_")[-1]==daml[k].split("_")[-1]
        try:

            # Dam polyline converted into polygon
            dampgon = arcpy.Buffer_analysis(in_features=daml[k], out_feature_class="dambuffer",
                                            buffer_distance_or_field="15 Meters", line_side="FULL", line_end_type="FLAT")

            # Erase underwater dam section
            dampgon = arcpy.Erase_analysis(in_features=dampgon, erase_features=resl[k], out_feature_class="damerase") # + resl[k].split("_")[-1]) if needed

            # Add Field to dam
            arcpy.AddField_management(in_table=dampgon, field_name="Index", field_type="TEXT")
            arcpy.CalculateField_management(in_table=dampgon, field="Index", expression='"{0}"'.format(daml[k]), expression_type="PYTHON")

            # Add Field to reservoir
            arcpy.AddField_management(in_table=resl[k], field_name="Index", field_type="TEXT")
            arcpy.CalculateField_management(in_table=resl[k], field="Index", expression='"{0}"'.format(resl[k]), expression_type="PYTHON")

            # Rounding
            integerfd = ["Water_area_ha", "Ground_area_ha", "Reservoir_volume_GL", "Dam_length_m", "Water_rock_ratio"]
            floatfd = ["Dam_area_ha", "Dam_volume_GL"]
            for fd in integerfd + floatfd:
                cursor = arcpy.SearchCursor(resl[k])
                row = cursor.next()
                if fd in integerfd:
                    fdvalue = int(float(row.getValue(fd)))
                elif fd in floatfd:
                    fdvalue = round(float(row.getValue(fd)), 1)
                arcpy.CalculateField_management(in_table=resl[k], field=fd, expression='"{0}"'.format(fdvalue), expression_type="PYTHON")

            # Attach dams to reservoirs
            # Note. "Union" creates 3 polygons while "Spatial Join" creates only 1; "Dissolve" aggregates features based on specified attributes.
            resdam = arcpy.Merge_management(inputs=[dampgon, resl[k]], output="resdammerge")

            # Delete Field
            AllField = [str(f.name) for f in arcpy.ListFields(resdam)]
            FieldList = ["OBJECTID", "Shape", "Lat", "Long", "Elevation_m", "Water_area_ha", "Ground_area_ha", "Reservoir_volume_GL",\
                         "Dam_length_m", "Dam_area_ha", "Dam_volume_GL", "Water_rock_ratio", "Index", "Shape_Length", "Shape_Area"]
            DropField = [f for f in AllField if f not in FieldList]
            arcpy.DeleteField_management(in_table=resdam, drop_field=DropField)
            
            # Smooth polygon edge
            resdam = arcpy.SmoothPolygon_cartography(in_features=resdam, out_feature_class="RESDAM_" + resl[k].split("_")[-1] + "_FC",
                                                     algorithm="PAEK", tolerance="90 Meters")

            # Create a KMZ file
            # layer.showLabels = True
            # http://desktop.arcgis.com/en/arcmap/10.3/manage-data/kml/creating-kml-in-arcgis-for-desktop.htm
            lyrresdam = arcpy.MakeFeatureLayer_management(in_features=resdam, out_layer="RESDAM_" + resl[k].split("_")[-1])
            arcpy.LayerToKML_conversion(layer=lyrresdam, out_kmz_file=os.path.join(directory, "RESDAM_" + resl[k].split("_")[-1] + ".kmz"))

            print "RESDAM_" + resl[k].split("_")[-1] + ".kmz saved"

        # Escape from an unexpected interruption
        except arcpy.ExecuteError as err:
            print "ArcPy ExecuteError: {0}".format(err)
            continue
        

if __name__=="__main__":
    
    # Record the start time and working environment
    starttime = dt.datetime.now()
    print "Begins at: " + str(starttime)
    print "ArcGIS version: " + arcpy.GetInstallInfo()["Version"]
    print "Workspace: " + arcpy.env.workspace
    print "Current working directory: " + os.getcwd()

    # Check/CheckOut the Spatial Analyst extension
    class LicenseError(Exception):
        pass
    
    try:
        if arcpy.CheckExtension("Spatial") == "Available":
            arcpy.CheckOutExtension("Spatial")
        else:
            raise LicenseError

        # Core
        resdamcr8()

        # CheckIn the Spatial Analyst extension
        arcpy.CheckInExtension("Spatial")
        
    except LicenseError:
        print("Spatial Analyst license is unavailable.")

    # Calculate the running time
    endtime = dt.datetime.now()
    print "Running time: " + str(endtime - starttime)
