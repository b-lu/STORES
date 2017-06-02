# Check 1 to 11 and run it within Python IDLE outside ArcMap
# Output: RES_1234, DAM_1234, records.csv
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

# Import the "DryGully" module
import DryGullyV20 as DryGully # Check 3

# Set input datasets and parameters
highland = "DEM_SA300UP" # Check 4 - Digital elevation model for the target region
direction = "SAFDIR" # Check 5 - Created from the tools Fill & Flow Direction
points = "SAPPT" # Check 6 - Pour points: at an inteval of 10 m height; slope < 1:5 (arctan); outside CAPAD
landslope = "SASLOPE" # Check 7 - A slope raster for the target region
maxdamheight = 40 # Check 8 - Max dam height: 40 m
minrescells = 111 # Check 9 - Min reservoir surface area: 10 ha (111 cells)
dambatter = 1 # Check 10 - Dam batter 1:1
screenrange = "All" # Check 11 - "All" or range(x ,y)


# Launch
if __name__=="__main__":

    # Record the start time and working environment
    starttime = dt.datetime.now()
    print "Begins at: " + str(starttime)
    print "ArcGIS version: " + arcpy.GetInstallInfo()["Version"]
    print "Workspace: " + arcpy.env.workspace
    print "Current working directory: " + os.getcwd()

    # Clear the record file (if there is)
    try:
        os.unlink(os.path.join(directory, "records.csv"))
    except OSError:
        pass
    
    # Check/CheckOut the Spatial Analyst extension
    class LicenseError(Exception):
        pass
    
    try:
        if arcpy.CheckExtension("Spatial") == "Available":
            arcpy.CheckOutExtension("Spatial")
        else:
            raise LicenseError

        # Core
        DryGully.screen() # Screen on a given DEM

        # CheckIn the Spatial Analyst extension
        arcpy.CheckInExtension("Spatial")
        
    except LicenseError:
        print("Spatial Analyst license is unavailable.")

    # Calculate the running time
    endtime = dt.datetime.now()
    print "Running time: " + str(endtime - starttime)
