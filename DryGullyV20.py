# This is the version 2.0 of the "DryGully" script - Identify prospective dry-gully sites for off-river PHES.
# 1. Remove the class DryGullySites and the def statistics(sites) as Add Field has already included the information.
# 2. Build an "user interface" - Interface.py
# 3. Fix a problem with 64-bit ArcGIS products: Tools that use VB expressions, such as Calculate Field, cannot use VB expressions in 64-bit ArcGIS products (ArcGIS for Server, ArcGIS for 64-bit Background Processing, and ArcGIS Runtime).
# 4. Add exception to escape from any unexpected interruption e.g. arcpy.ExecuteError or RuntimeError.
# Bug reports to: bin.lu@anu.edu.au

import os
import sys
import arcpy
import math
import csv
from Interface import directory, highland, direction, points, landslope, maxdamheight, minrescells, dambatter, screenrange


def screen():

    # Number of pour points
    arcpy.env.extent = points
    print "Number of pour points: " + str(int(arcpy.GetCount_management(points).getOutput(0)))

    # Calculation on each of the pour points
    with arcpy.da.SearchCursor(points, "OBJECTID") as cursor:
        for idx in cursor:
            try:
                # Calculate All the points or just a given range
                if screenrange=="All":
                    pass
                else:
                    if idx[0] not in screenrange:
                        continue

                # Select a pour point from the layer
                arcpy.env.extent = points # Recover the Processing Extent
                lyrpp = arcpy.MakeFeatureLayer_management(in_features=points, out_layer="pptlayer" + str(idx[0]),
                                                          where_clause="OBJECTID = " + str(idx[0])) # a layer of a pour point
                point = arcpy.CopyFeatures_management(in_features=lyrpp, out_feature_class="appt" + str(idx[0]))

                # Get the coordinates
                cursor = arcpy.SearchCursor(point)
                row = cursor.next()
                latitude = row.getValue("POINT_Y")
                longitude = row.getValue("POINT_X")

                # Reduce the Processing Extent
                arcpy.env.extent = arcpy.Extent(longitude-0.05, latitude+0.05, longitude+0.05, latitude-0.05)

                # Calculate watershed and reservoir
                watershed = arcpy.gp.Watershed_sa(direction, point, "wshed" + str(idx[0]), "OBJECTID") # Define a watershed
                watershed = arcpy.gp.ExtractByMask_sa(highland, watershed) # Get the DEM of a watershed
                watershed = arcpy.Raster(watershed)
                elevpoint = watershed.minimum
                if elevpoint==None:
                    print "Watershed of Point " + str(idx[0]) + " is None (ignored)."
                    continue
                reservoir = arcpy.gp.ExtractByAttributes_sa(watershed, "VALUE <= " + str(elevpoint + maxdamheight)) 

                # Calculate the area of a reservoir in cells
                with arcpy.da.SearchCursor(reservoir, "COUNT") as cursor:
                    cells = sum([c[0] for c in cursor]) # number of cells
                print "RES_" + str(idx[0]) + ": " + str(cells) + " cells"

                # Output a polygon that meets the criterion
                if cells<minrescells:
                    continue
                else:
                    watershed_polygon = arcpy.RasterToPolygon_conversion(in_raster=watershed * 0,
                                                                         out_polygon_features="wshedpolygon" + str(idx[0]),
                                                                         simplify="NO_SIMPLIFY")
                    reservoir = arcpy.Raster(reservoir)
                    reservoir_polygon = arcpy.RasterToPolygon_conversion(in_raster=reservoir * 0,
                                                                         out_polygon_features="respolygon" + str(idx[0]),
                                                                         simplify="NO_SIMPLIFY")
                   
                # If there is an isolated tiny polygon?
                rescount = int(arcpy.GetCount_management(reservoir_polygon).getOutput(0))
                if rescount>1:
                    with arcpy.da.SearchCursor(reservoir_polygon, "SHAPE_AREA") as cursor:
                        maxresarea = max([a[0] for a in cursor])
                    lyrres = arcpy.MakeFeatureLayer_management(in_features=reservoir_polygon, out_layer="areslayer" + str(idx[0]),
                                                               where_clause="SHAPE_AREA = " + str(maxresarea)) # a layer of a polygon
                    reservoir_polygon = arcpy.CopyFeatures_management(in_features=lyrres, out_feature_class="respolygon1" + str(idx[0]))
                assert int(arcpy.GetCount_management(reservoir_polygon).getOutput(0))==1

                # Write the coordinates
                coordinates = str(latitude) + "   " + str(longitude)
                fieldlot = []
                fieldlot.append(("Lat", latitude))
                fieldlot.append(("Long", longitude))

                # Derive the elevation of a reservoir/dam/pour point
                elevation = elevpoint
                fieldlot.append(("Elevation_m", elevpoint))

                # Calculate the average slope of a reservoir
                resslope = arcpy.gp.ExtractByMask_sa(landslope, reservoir_polygon) # Get the DEM of a watershed
                resslope = arcpy.Raster(resslope)

                # Project to GDA 1994 Geoscience Australia Lambert: 3112
                # GCS_WGS_1984: 4326
                reservoir_polygongda94 = arcpy.Project_management(in_dataset=reservoir_polygon,
                                                                  out_dataset="respolygongda94_" + str(idx[0]),
                                                                  out_coor_system=arcpy.SpatialReference(3112),
                                                                  transform_method="GDA_1994_To_WGS_1984",
                                                                  in_coor_system=arcpy.SpatialReference(4326))
                
                # Calculate the area of a reservoir (in hectares)
                with arcpy.da.SearchCursor(reservoir_polygongda94, "SHAPE_AREA") as cursor:
                    waterarea = cursor.next()[0] * pow(10, -4) # hectares
                groundarea = waterarea / math.cos(math.radians(resslope.mean)) if resslope.mean!=0 else waterarea
                fieldlot.append(("Water_area_ha", waterarea))
                fieldlot.append(("Ground_area_ha", groundarea))
                
                # Calculate the volume of a reservoir in GL
                resvolume = waterarea * (elevpoint + maxdamheight - reservoir.mean) * pow(10, -2) # GL
                fieldlot.append(("Reservoir_volume_GL", resvolume))

                # Build a dam
                dam_polyline = arcpy.Intersect_analysis(in_features=[watershed_polygon, reservoir_polygon],
                                                        out_feature_class="DAM_" + str(idx[0]),
                                                        output_type="LINE")

                # Project to GDA 1994 Geoscience Australia Lambert: 3112
                # GCS_WGS_1984: 4326
                dam_polylinegda94 = arcpy.Project_management(in_dataset=dam_polyline,
                                                             out_dataset="dampolylinegda94_" + str(idx[0]),
                                                             out_coor_system=arcpy.SpatialReference(3112),
                                                             transform_method="GDA_1994_To_WGS_1984",
                                                             in_coor_system=arcpy.SpatialReference(4326))

                # Calculate the length of a dam in metres
                with arcpy.da.SearchCursor(dam_polylinegda94, "SHAPE_LENGTH") as cursor:
                    damlength = cursor.next()[0] # metres
                fieldlot.append(("Dam_length_m", damlength))

                # Get the DEM of a dam
                dam = arcpy.gp.ExtractByMask_sa(highland, dam_polyline)
                dam = arcpy.Raster(dam)

                # Calculate the inside area of a dam in hectares
                damarea = damlength * (elevpoint + maxdamheight - dam.mean) * pow(10, -4) / math.cos(math.atan(dambatter)) # hectares
                fieldlot.append(("Dam_area_ha", damarea))

                # Calculate the volume of a dam in GL
                damvolume = damlength * (elevpoint + maxdamheight - dam.mean)**2 * pow(10, -6) * dambatter # GL
                fieldlot.append(("Dam_volume_GL", damvolume))

                # Add the half dam volume to reservoir
                resvolume += 0.5 * damvolume
                for i, t in enumerate(fieldlot):
                    if t[0]=="Reservoir_volume_GL":
                        fieldlot[i] = ("Reservoir_volume_GL", resvolume)

                # Calculate the water/rock ratio
                wrratio = resvolume / float(damvolume) if damvolume!=0 else 0
                fieldlot.append(("Water_rock_ratio", wrratio))

                # Add Field
                for f in fieldlot:
                    arcpy.AddField_management(in_table=reservoir_polygon, field_name=f[0], field_type="TEXT")
                    arcpy.CalculateField_management(in_table=reservoir_polygon, field=f[0], expression=str(f[1]), expression_type="PYTHON")

                # Get RES_1234
                arcpy.CopyFeatures_management(in_features=reservoir_polygon, out_feature_class="RES_" + str(idx[0]))

            # Escape from any unexpected interruption
            except arcpy.ExecuteError as err:
                print "ArcPy ExecuteError: {0}".format(err)
                continue
            except RuntimeError:
                print "Python RuntimeError: ", sys.exc_info()[0]
                continue

            # Record the information for each site
            with open(os.path.join(directory, "records.csv"), "a") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(("RES_" + str(idx[0]), coordinates, elevation, waterarea, groundarea, resvolume, damlength, damarea, damvolume, wrratio))
                
