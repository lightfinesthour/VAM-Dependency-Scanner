#!/usr/bin/python3
from zipfile import ZipFile
from glob import glob
from os.path import join, split, splitext, exists, basename, isdir, dirname, abspath
import sys
import argparse
from pathlib import Path
from json import load
import re
import os
import traceback
import shutil

def dpPrint(text: str, toFile: str = ''):
    print(text, flush=True)
    if toFile:
        try:
            with open(toFile, 'a', encoding='utf-8') as f:
                f.write(text + '\n')
        except Exception as error:
            print(f"ERROR, failed to write to {toFile}: {error}", file=sys.stderr, flush=True)
            return

def check_name_variation(varName, dependenciesList):
    parts = varName.split('.')
    if parts[-1].isdigit() or parts[-1] == 'latest':
        baseName = '.'.join(parts[:-1])
    else:
        baseName = varName
    return varName in dependenciesList or f'{baseName}.latest' in dependenciesList

def getDependencies(varFile: str) -> tuple[Exception|None, set]:
    try:
        with ZipFile(varFile) as myzip:
            try:
                with myzip.open('meta.json') as metaJson:
                    data = load(metaJson)
            except KeyError:
                # meta.json not found in the zip
                return Exception(f"meta.json not found in {varFile}"), set()
            finally:
                myzip.close()

        if 'dependencies' not in data:
            return None, set()
        return None, set(data['dependencies'].keys())
    except Exception as error:
        return error, set()

# Safely get all files matching a pattern
def safe_glob(pattern):
    try:
        return glob(pattern, recursive=True)
    except Exception as e:
        dpPrint(f"WARNING: Error while searching for files matching {pattern}: {e}", args.output)
        return []

# Get all dependencies listed in presets
def getPresetDependencies(customPath: str) -> dict:
    allDependencies = {}
    try:
        customPathFull = join(customPath, 'Custom')
        if not exists(customPathFull):
            dpPrint(f"WARNING: Custom path does not exist: {customPathFull}", args.output)
            return allDependencies

        presets = sorted(safe_glob(join(customPathFull, '**/*.vap')))
        dpPrint(f"Found {len(presets)} preset files in {customPathFull}", args.output)

        for vap in presets:
            try:  
                with open(vap, 'r', encoding='utf-8') as f:
                    pattern = r'"([^"]+):/[^"]*"'
                    occurences = set(re.findall(pattern, f.read()))
            except Exception as error:
                dpPrint(f"ERROR, failed to read: {vap}: {error}", args.output)
                continue

            try:
                parts = Path(vap).parts
                custom_index = -1
                for i, part in enumerate(parts):
                    if part == "Custom":
                        custom_index = i
                        break
                
                if custom_index >= 0 and custom_index < len(parts) - 1:
                    presetName = '/'.join(parts[custom_index+1:])
                else:
                    presetName = basename(vap)
                    
                dependenciesDict = {key: {presetName} for key in occurences}
                for key, val in dependenciesDict.items():
                    if key in allDependencies:
                        allDependencies[key].update(val)
                    else:
                        allDependencies[key] = val
            except Exception as error:
                dpPrint(f"ERROR processing preset dependencies in {vap}: {error}", args.output)
                continue
    except Exception as error:
        dpPrint(f"ERROR in getPresetDependencies: {error}", args.output)
        dpPrint(traceback.format_exc(), args.output)
    
    return allDependencies

# Collect all vars, a complete list of all dependencies, and which vars uses which dependency
def getAllVars(directoryPath: str) -> tuple[set, dict]:
    allDependencies = {}
    allVarList = set()

    try:
        addon_path = join(directoryPath, 'AddonPackages')
        if not exists(addon_path):
            dpPrint(f"WARNING: AddonPackages path does not exist: {addon_path}", args.output)
            # Try directly in the directory instead
            vars = safe_glob(join(directoryPath, '**/*.var'))
        else:
            vars = safe_glob(join(addon_path, '**/*.var'))
        
        dpPrint(f"Found {len(vars)} var files to process", args.output)
        
        for var in vars:
            try:
                allVarList.add(splitext(basename(var))[0])
            except Exception as e:
                dpPrint(f"ERROR processing filename {var}: {e}", args.output)

        for varFilename in vars:
            try:
                if isdir(varFilename):
                    error, dependencies = getMetaDependencies(varFilename)
                else:
                    error, dependencies = getDependencies(varFilename)

                if (isinstance(error, Exception)):
                    dpPrint(f"ERROR: {varFilename}: {error}", args.output)
                    continue

                if (len(dependencies) == 0):
                    continue

                var_basename = basename(varFilename)
                dependenciesDict = {key: {var_basename} for key in dependencies}
                for key, val in dependenciesDict.items():
                    if key in allDependencies:
                        allDependencies[key].update(val)
                    else:
                        allDependencies[key] = val
            except Exception as e:
                dpPrint(f"ERROR processing dependencies for {varFilename}: {e}", args.output)
                continue
    except Exception as error:
        dpPrint(f"ERROR in getAllVars: {error}", args.output)
        dpPrint(traceback.format_exc(), args.output)

    return allVarList, allDependencies

# Get all dependencies listed in meta.json stored directly in folders
def getMetaDependencies(folder: str) -> tuple[Exception|None, set]:
    filename = join(folder, 'meta.json')
    try:
        with open(filename, 'r', encoding='utf-8') as metaJson:
            data = load(metaJson)

        if 'dependencies' not in data:
            return None, set()
        return None, set(data['dependencies'].keys())
    except Exception as error:
        return error, set()

# Find the best match for a dependency in source files
def find_dependency_match(dependency, sourceVarFiles):
    # Exact match
    for source_file in sourceVarFiles:
        source_name = splitext(basename(source_file))[0]
        if source_name == dependency:
            return source_file
    
    # If dependency ends with .latest, look for the highest version
    if dependency.endswith('.latest'):
        base_name = dependency[:-7]  # Remove '.latest'
        matching_files = []
        
        for source_file in sourceVarFiles:
            source_name = splitext(basename(source_file))[0]
            if source_name.startswith(base_name + '.'):
                # Get the version number
                try:
                    version_part = source_name[len(base_name)+1:]
                    if version_part.isdigit():
                        matching_files.append((int(version_part), source_file))
                except:
                    pass
        
        if matching_files:
            # Sort by version number (highest first)
            matching_files.sort(reverse=True)
            return matching_files[0][1]
    
    # Try to find any version of the dependency
    parts = dependency.split('.')
    if len(parts) > 1:
        base_name = '.'.join(parts[:-1])
        matching_files = []
        
        for source_file in sourceVarFiles:
            source_name = splitext(basename(source_file))[0]
            if source_name.startswith(base_name + '.'):
                try:
                    version_part = source_name[len(base_name)+1:]
                    if version_part.isdigit():
                        matching_files.append((int(version_part), source_file))
                except:
                    pass
        
        if matching_files:
            # Sort by version number (highest first)
            matching_files.sort(reverse=True)
            return matching_files[0][1]
    
    return None

def checkMissingReferences(mainPath: str, sourcePath: str, destPath: str = None) -> dict:
    try:
        dpPrint(f"Getting dependencies from main path: {mainPath}", args.output)
        mainVarList, mainDependencies = getAllVars(mainPath)
        dpPrint(f"Found {len(mainDependencies)} dependencies in main path", args.output)
        dpPrint(f"Found {len(mainVarList)} var files in main path", args.output)
        
        dpPrint(f"Getting available var files from source path: {sourcePath}", args.output)
        # Don't require AddonPackages folder in source directory
        sourceVarFiles = safe_glob(join(sourcePath, '**/*.var'))
        dpPrint(f"Found {len(sourceVarFiles)} var files in source path", args.output)
        
        sourceVarList = set()
        sourceVarDict = {}  # Map names to file paths
        
        for var in sourceVarFiles:
            try:
                var_name = splitext(basename(var))[0]
                sourceVarList.add(var_name)
                sourceVarDict[var_name] = var
            except Exception as e:
                dpPrint(f"ERROR processing source filename {var}: {e}", args.output)
        
        dpPrint(f"Processing {len(sourceVarList)} unique var names from source", args.output)
        
        # Create destination directory if needed and copying is enabled
        if destPath:
            os.makedirs(destPath, exist_ok=True)
            dpPrint(f"Will copy found dependencies to: {destPath}", args.output)
        
        # Find missing dependencies
        missingRefs = {}
        foundRefs = {}
        alreadySatisfiedRefs = {}
        
        for dependency, dependents in mainDependencies.items():
            try:
                # Skip empty dependencies
                if not dependency or dependency.isspace():
                    continue
                
                # Check if dependency already exists in the main path
                dependency_already_exists = False
                for var_name in mainVarList:
                    if var_name == dependency or (dependency.endswith('.latest') and var_name.startswith(dependency[:-7])):
                        dependency_already_exists = True
                        alreadySatisfiedRefs[dependency] = {
                            'satisfied_by': var_name,
                            'dependents': dependents
                        }
                        break
                
                if dependency_already_exists:
                    if args.verbose:
                        dpPrint(f"Dependency already satisfied: {dependency}", args.output)
                    continue
                
                # Find the best matching file for this dependency
                match_file = find_dependency_match(dependency, sourceVarFiles)
                
                if match_file:
                    # We found a match
                    foundRefs[dependency] = {
                        'file': match_file,
                        'dependents': dependents
                    }
                    
                    # Copy file if destPath is provided
                    if destPath:
                        dest_file = join(destPath, basename(match_file))
                        if not exists(dest_file):
                            try:
                                shutil.copy2(match_file, dest_file)
                                dpPrint(f"Copied: {basename(match_file)} -> {dest_file}", args.output)
                            except Exception as e:
                                dpPrint(f"ERROR copying {match_file} to {dest_file}: {e}", args.output)
                else:
                    # No match found
                    missingRefs[dependency] = dependents
            except Exception as e:
                dpPrint(f"ERROR checking dependency {dependency}: {e}", args.output)
                continue
                
        # Report statistics
        dpPrint(f"Dependencies already satisfied: {len(alreadySatisfiedRefs)}", args.output)
        dpPrint(f"Found matches for {len(foundRefs)} dependencies", args.output)
        dpPrint(f"Missing {len(missingRefs)} dependencies", args.output)
        
        if destPath:
            dpPrint(f"Copied dependencies to: {destPath}", args.output)
            
        if args.verbose and alreadySatisfiedRefs:
            dpPrint("\nAlready satisfied dependencies:", args.output)
            for dep, info in alreadySatisfiedRefs.items():
                dpPrint(f"  {dep} (satisfied by: {info['satisfied_by']})", args.output)
            
        return missingRefs, foundRefs
    except Exception as error:
        dpPrint(f"ERROR in checkMissingReferences: {error}", args.output)
        dpPrint(traceback.format_exc(), args.output)
        return {}, {}

def main():
    global args
    
    argParser = argparse.ArgumentParser(prog='DependencyScanner.py', 
                                       description='Searches for dependencies inside all vars in a folder and if a name is given, lists whether there a vars that depend on it. If no name is given, it will instead list all vars in the folder which isn\'t a dependency of any other var.')
    argParser.add_argument("-p", "--path",
                          type=str,
                          default='.',
                          help="Path to your VaM folder")
    argParser.add_argument("-s", "--source",
                          type=str,
                          default=None,
                          help="Path to source folder with extra .var files to check for missing references")
    argParser.add_argument("-n", "--name",
                          type=str,
                          default='',
                          help="Name of a var file. Can be a partial name")
    argParser.add_argument("-o", "--output",
                          type=str,
                          nargs='?',
                          default=None,
                          const='SearchVarOutput.txt',
                          help="File to save the results in (default: 'SearchVarOutput.txt')")
    argParser.add_argument("-m", "--missing-only",
                          action="store_true",
                          help="Only show missing references")
    argParser.add_argument("-v", "--verbose",
                          action="store_true",
                          help="Show verbose output")
    argParser.add_argument("-d", "--dest",
                          type=str,
                          default=None,
                          help="Destination folder to copy found dependencies to")
    argParser.add_argument("-c", "--copy-found",
                          action="store_true",
                          help="Copy found dependencies to the destination folder")

    args = argParser.parse_args()

    # Convert to absolute paths
    args.path = abspath(args.path)
    if args.source:
        args.source = abspath(args.source)
    if args.output:
        args.output = abspath(args.output)
    if args.dest:
        args.dest = abspath(args.dest)

    # Check the given arguments are valid
    if not exists(args.path):
        print(f"The given path doesn't exist: {args.path}")
        return 1

    if args.source and not exists(args.source):
        print(f"The given source path doesn't exist: {args.source}")
        return 1

    if args.copy_found and not args.dest:
        print("A destination folder (--dest) must be specified when using --copy-found")
        return 1

    if args.output:
        output_dir = dirname(args.output)
        if output_dir and not exists(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
                print(f"Created output directory: {output_dir}")
            except Exception as e:
                print(f"Failed to create output directory {output_dir}: {e}")
                return 1
                
        try:
            open(args.output, 'w', encoding='utf-8').close()
        except Exception as e:
            print(f"Failed to create/open output file {args.output}: {e}")
            return 1

    parts = args.name.split('.')
    if parts[-1] == 'var':
        args.name = '.'.join(parts[:-1])

    if args.verbose:
        dpPrint(f"Starting dependency scan with arguments:", args.output)
        dpPrint(f"  Path: {args.path}", args.output)
        dpPrint(f"  Source: {args.source}", args.output)
        dpPrint(f"  Name: {args.name}", args.output)
        dpPrint(f"  Output: {args.output}", args.output)
        dpPrint(f"  Missing only: {args.missing_only}", args.output)
        if args.copy_found:
            dpPrint(f"  Copying found dependencies to: {args.dest}", args.output)
        dpPrint("", args.output)

    # Check for missing references and copy found dependencies if requested
    if args.source:
        dpPrint("Checking for missing references...", args.output)
        
        # Determine if we need to copy found dependencies
        dest_path = args.dest if args.copy_found else None
        
        # Run the dependency check
        missingRefs, foundRefs = checkMissingReferences(args.path, args.source, dest_path)
        
        # Report on missing references
        if missingRefs:
            dpPrint(f"\nFound {len(missingRefs)} missing references:", args.output)
            for missingRef, dependents in missingRefs.items():
                dpPrint(f"  Missing: {missingRef}", args.output)
                dpPrint(f"  Required by:", args.output)
                for dependent in sorted(dependents):
                    dpPrint(f"    - {dependent}", args.output)
                dpPrint("", args.output)
        else:
            dpPrint("No missing references found.", args.output)
        
        # Report on found references if verbose
        if args.verbose and foundRefs:
            dpPrint(f"\nFound {len(foundRefs)} references:", args.output)
            for foundRef, info in foundRefs.items():
                dpPrint(f"  Found: {foundRef}", args.output)
                dpPrint(f"  Source: {info['file']}", args.output)
                dpPrint(f"  Required by:", args.output)
                for dependent in sorted(info['dependents']):
                    dpPrint(f"    - {dependent}", args.output)
                dpPrint("", args.output)
        
        if args.missing_only:
            if args.output:
                print(f"\nResults saved to: {args.output}")
            return 0

    # Get a list of all vars and a dict of all dependencies from vars
    allVarList, allVarDependencies = getAllVars(args.path)
    allDepVars = list(allVarDependencies.keys())

    # Get a dict of all dependencies from presets
    allPresetDependencies = getPresetDependencies(args.path)
    allDepVarsPresets = list(allPresetDependencies.keys())

    # Combine all dependencies
    allDependencies = {**allVarDependencies}
    for key, val in allPresetDependencies.items():
        if key in allDependencies:
            allDependencies[key].update(val)
        else:
            allDependencies[key] = val

    # Get a list of which vars in the folder that are not used as a dependency
    noDependencyVar = [var for var in allVarList if not check_name_variation(var, allDepVars)]
    noDependencyPreset = [var for var in allVarList if not check_name_variation(var, allDepVarsPresets)]
    noDependency = sorted(list(set(noDependencyVar) & set(noDependencyPreset)), key=str.lower)

    # If no name is given, list all vars that aren't used as a dependency
    if args.name == '':
        dpPrint(f"{len(noDependency)} vars are not used as a dependency:", args.output)
        for var in noDependency:
            dpPrint("\t" + var, args.output)
        if args.output:
            print(f"\nResults saved to: {args.output}")
        return 0

    # List all vars with the given name that aren't used as a dependency
    foundVars = [var for var in noDependency if args.name.lower() in var.lower()]
    if len(foundVars) > 0:
        dpPrint(f"The following {str(len(foundVars)) + ' vars are' if len(foundVars) > 1 else 'var is'} not used as a dependency in other vars:", args.output)
        for var in foundVars:
            dpPrint("\t" + var, args.output)

    # List all vars with the given name that depend on other vars
    foundDepVars = sorted([var for var in allDependencies.keys() if args.name.lower() in var.lower()], key=str.lower)
    if len(foundDepVars) > 0:
        dpPrint(f"\nThe following {len(foundDepVars)} iteration{'s' if len(foundDepVars) > 1 else ''} of '" + args.name + "' has other vars that depend on it:", args.output)

        # print all dependencies where the name is a key, or the name is part of the key
        for key in foundDepVars:
            if args.name.lower() in key.lower():
                if args.name != key:
                    dpPrint(f"{key} ->", args.output)
                for var in sorted(allDependencies[key], key=str.lower):
                    dpPrint("\t" + var, args.output)

    if args.output:
        print(f"\nResults saved to: {args.output}")
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"Unhandled exception: {e}")
        print(traceback.format_exc())
        sys.exit(1)
