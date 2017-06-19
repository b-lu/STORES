# This script is to seperate a state/region into potential locations for upper and lower reservoirs of off-river PHES.
# Check 1 to 7: Head (altitude difference) and head to horizontal distance ratio can be specified.
# Output: DEM_SA300UP for DryGully.py
# Bug reports to: bin.lu@anu.edu.au

import os
import arcpy
import datetime as dt

# Set working directory and geodatabase
directory = r"D:\SA" # Check 1
geodatabase = "SA_PHSites.gdb" # Check 2
arcpy.env.workspace = os.path.join(directory, geodatabase)
arcpy.env.addOutputsToMap = False
arcpy.env.parallelProcessingFactor = "75%"
arcpy.env.overwriteOutput = True
os.chdir(directory)

# Set input datasets and parameters
region = "SAEG" # Check 3 - Name of the target region: SAEG is an example of SA
demodel = "DEM_SAEG" # Check 4 - Digital elevation model for the target region
heads = range(200, 501, 100) # Check 5 - Altitude difference
slopes = [15] # Check 6 - Head to horizontal distance ratio
resolution = 30 # Check 7 - Approx. 30 m for 1 arc-second DEM of SA


def landsep(head, slope, cellsize):

    # "MINIMUM" for upper reservoirs while "MAXIMUM" for lower reservoirs
    for stat in [("MINIMUM", "UP"), ("MAXIMUM", "LOW")]:

        # Focal Statistics
        outrasfs = os.path.join("in_memory", region + str(head) + stat[0][:3])
        nbrhd = "Circle " + str(head * slope / cellsize) + " CELL" # e.g. 300 m - 4.5 km - 150 cells
        arcpy.gp.FocalStatistics_sa(demodel, outrasfs, nbrhd, stat[0], "DATA")
        print stat[0] + " Focal Statistics finished at " + str(dt.datetime.now())

        # Raster Calculator
        elevdiff = demodel - arcpy.Raster(outrasfs)
        print stat[0] + " Raster Calculator finished at " + str(dt.datetime.now())
        
        # Set Null
        outrassn = os.path.join("in_memory", region + str(head) + stat[1])
        wherec = "Value <= " + str(head) if stat[0]=="MINIMUM" else "Value >= " + str(-1 * head)
        arcpy.gp.SetNull_sa(elevdiff, "-999", outrassn, wherec)
        print stat[0] + " Set Null finished at " + str(dt.datetime.now())

        # Extract by Mask
        if stat[1]=="LOW":
            continue
        outrasem = "DEM_" + region + str(head) + stat[1]
        arcpy.gp.ExtractByMask_sa(demodel, outrassn, outrasem)
        

if __name__=='__main__':
    
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
        for head in heads:
            for slope in slopes:
                landsep(head=head, slope=slope, cellsize=resolution)

        # CheckIn the Spatial Analyst extension
        arcpy.CheckInExtension("Spatial")
        
    except LicenseError:
        print("Spatial Analyst license is unavailable.")

    # Calculate the running time
    endtime = dt.datetime.now()
    print "Running time: " + str(endtime - starttime)
