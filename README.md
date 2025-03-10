# VAM Dependency Scanner

A Python utility for analyzing and managing dependencies in Virt-A-Mate (VAM) packages (.var files). This tool helps you identify missing dependencies, find unused packages, and automatically copy required dependencies from a source folder.

## Features

- Scan your VAM directory to identify all package dependencies
- Find packages that aren't used as dependencies by any other package
- Identify dependencies that are missing from your collection
- Check if specific packages are used as dependencies
- Copy found dependencies from a source directory to a destination directory
- Generate detailed reports of dependency relationships

## Requirements

- Python 3.6 or higher
- No external dependencies beyond the Python standard library

## Installation

1. Clone this repository or download the `DependencyScanner.py` script
2. Make sure you have Python 3.6+ installed on your system
3. No additional packages need to be installed

## Usage

```
python DependencyScanner.py [options]
```

### Basic Options

- `-p, --path PATH`: Path to your main VAM folder (default: current directory)
- `-s, --source PATH`: Path to source folder with additional .var files to check for missing references
- `-n, --name NAME`: Name of a specific var file to search for (can be a partial name)
- `-o, --output [FILE]`: File to save the results in (default if flag used without value: 'SearchVarOutput.txt')
- `-m, --missing-only`: Only show missing references in the output
- `-v, --verbose`: Show verbose output with additional details
- `-d, --dest PATH`: Destination folder to copy found dependencies to
- `-c, --copy-found`: Copy found dependencies to the destination folder (requires --dest)

### Examples

#### List all packages not used as dependencies by any other package

```
python DependencyScanner.py -p "C:\VAM"
```

#### Search for a specific package and check if others depend on it

```
python DependencyScanner.py -p "C:\VAM" -n "MeshedVR"
```

#### Find all missing dependencies by comparing two directories

```
python DependencyScanner.py -p "C:\VAM" -s "D:\VAM_Backups\Packages" -m
```

#### Copy missing dependencies from a source directory to a destination

```
python DependencyScanner.py -p "C:\VAM" -s "D:\VAM_Backups\Packages" -d "C:\VAM\AddonPackages" -c
```

#### Save the scan results to a file

```
python DependencyScanner.py -p "C:\VAM" -o "dependency_report.txt"
```

## How It Works

The script performs the following operations:

1. Scans all .var files in the specified VAM directory (and its subdirectories)
2. Extracts dependency information from the meta.json file inside each .var package
3. Also analyzes .vap preset files to find additional dependencies
4. Builds a dependency graph showing which packages are used by others
5. When checking for missing references, it intelligently handles version numbers and .latest suffixes
6. Can automatically copy found dependencies to help complete your collection

## Output Example

```
Getting dependencies from main path: E:\Games\VAM
Found 325 dependencies in main path
Getting available var files from source path: D:\VAM_Backups
Found 1250 var files in source path
Processing 1248 unique var names from source

Found matches for 315 dependencies
Missing 10 dependencies

Found 10 missing references:
  Missing: Custom.SomeDependency.1
  Required by:
    - MyPackage.1.var

  Missing: Another.Package.latest
  Required by:
    - OtherPackage.3.var
    - SomePackage.2.var
```

## Notes

- The script handles version numbers in package names (e.g., "Package.1" vs "Package.2")
- It also properly processes .latest dependencies, finding the highest available version
- When copying found dependencies, it preserves the original filenames
- All paths are converted to absolute paths for consistency

## Contributing

Contributions are welcome! Feel free to submit issues or pull requests.

## License

[MIT License](LICENSE)
