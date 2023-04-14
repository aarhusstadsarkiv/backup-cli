import json
import sys
from pathlib import Path
import csv
import argparse
from typing import List, Tuple, Optional, Sequence
# from importlib import metadata
from filter_csv_generic.settings import FIELDS, FIELDS_TRANSLATED


def get_version() -> str:
    version = "Ukendt version"
    # with open(Path(__file__).absolute().parent.parent / "pyproject.toml") as i:
    #     for line in i.readlines():
    #         if line.startswith("version"):
    #             version = line[line.index('"') + 1 : -2]
    return version  # metadata.version("filter_csv_generic")


def main(argv: Optional[Sequence[str]] = None) -> int:

    output: List[Tuple[int, int, int]] = []

    parser = argparse.ArgumentParser(
        description=(
            "Filters the csv formatted backup database:\n"
            "Apply any number of --filter \n"
            "Use --list for allowed fields and operators.\n"
            "Use --filename to specify a custom filename for the output file(s).\n"
            "\n\n"
            'ex.1 field is "id-field"\n'
            "--filter Samling equalTo 1\n"
            "or\n"
            "--filter Samling contains Salling\n\n"
            "ex.2 if the field is a dictionary, and target search is in a key's value:\n"
            '--filter "Administrative data" contains '
            '"Bestillingsinformation:negativsamlingen 1970"\n\n'
            "ex.3 if the field is a dictionary, and filter after target has a certain key:\n"
            '--filter "Administrative data" hasKey Bestillingsinformation\n\n'
            "ex.4 the field is a dictionary and the key is known and filter on the value:\n"
            '--filter "Beskrivelsesdata" contains Typer:Farve\n\n'
            'ex.5 use the "null" keyword to filter for any entry has a certain field:\n'
            '--filter Samling equalTo null or --filter Samling notEqualTo null\n\n'
            'All user inputs are case-insensitive. Field names are case-sensitive.'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "csv_path",
        metavar="input_csv_file_path",
        type=str,
        nargs="?",
        help="Path to the backup database csv file.",
    )
    parser.add_argument(
        "output_path",
        metavar="output_dir",
        type=str,
        nargs="?",
        help="Path to the output/result directory for csv file(s).",
    )
    parser.add_argument(
        "--print", action="store_true", help="If the results are few, prints the results instead of generating csv file(s)."
    )
    parser.add_argument(
        "--filter",
        type=str,
        nargs=3,
        action="append",
        help=("Adds a filter to limit the results"),
    )

    parser.add_argument(
        "--version",
        action="version",
        version=get_version(),
        help="States the current version of this CLI.",
    )
    parser.add_argument(
        "--list", action="store_true", help="Lists the allowed fields and their operators."
    )

    parser.add_argument(
        "--filename", type=str, nargs=1, action="append", help="specify the output filename(s)."
    )#remove action?
    parser.add_argument("--or_", action="store_true", help="the filters are or'ed together.")

    parser.add_argument(
        "--field", type=str, nargs=1, action="append", help="if specified, adds extra data field in results file(s)."
    )

    args = parser.parse_args(argv)

    def list_fields() -> None:
        print("Printing fields and operators...")
        for key in FIELDS_TRANSLATED.keys():
            print(key.ljust(25), end="")
            print(", ".join(FIELDS[FIELDS_TRANSLATED[key]].keys()))

    if args.list:
        list_fields()
        sys.exit(0)

    if args.csv_path:
        input_csv = Path(args.csv_path)
    if args.output_path:
        output_dir = Path(args.output_path)

    

    filters: List[List[str]] = args.filter
    extra_fields: List[List[str]] = args.field

    if args.field:
        header_print: List[str] = []
        header_print.append("id")
        for field in args.field:
            
            header_print.append(field[0])            

    # -----input validation-------------------------------------------------
    if not args.csv_path:
        sys.exit("No input csv database backup given...")

    if not args.filter:
        sys.exit("No filters were given...")    

    csv_path = input_csv
    if not csv_path.suffix == ".csv":
        sys.exit("input file is not a csv-file...")

    if not csv_path.exists():
        sys.exit("input csv-file does not exists...")

    if not args.output_path and not args.print:
        sys.exit("No output path or --print...")

    if args.output_path and not output_dir.exists():
        sys.exit("output directory does not exists. Please create one...")
    # ----------------------------------------------------------------------

    print("Starting filtering process...")
    with open(csv_path, encoding="utf-8") as csvf:
        csvReader = csv.DictReader(csvf)

        for row in csvReader:
            _dict: dict = json.loads(row["oasDictText"])            

            operators_results: List[bool] = []

            for i in range(len(filters)):  # i is filter No.

                fieldname: str = args.filter[i][0]
                fieldname = FIELDS_TRANSLATED[fieldname]

                operator_key: str = args.filter[i][1]
                fieldvalue: str = args.filter[i][2]
                fieldvalue = fieldvalue.lower()

                if (
                    fieldvalue == "null"
                    and operator_key == "equalTo"
                    and not _dict.get(fieldname)
                ):
                    op_results = True
                elif (
                    fieldvalue == "null"
                    and operator_key == "notEqualTo"
                    and _dict.get(fieldname)
                ):
                    op_results = True
                elif not _dict.get(fieldname):
                    op_results = False
                else:
                    operator = FIELDS[fieldname][operator_key]
                    op_results = operator(_dict[fieldname], fieldvalue)

                operators_results.append(op_results)

            if args.or_:
                total_op_result = any(operators_results)
            else:
                total_op_result = all(operators_results)

            if not total_op_result:
                continue  # if false
            
            id = row["id"]
            header: List[str] = ["id"]
            to_add: List[str] = [id]

            if extra_fields:
                for field in extra_fields:
                    
                    header.append(field[0])

                    fieldname = FIELDS_TRANSLATED[field[0]]
                    fieldvalue_ = _dict.get(fieldname, "")
                    
                    to_add.append(json.dumps(fieldvalue_, ensure_ascii=False))

            output.append(to_add)   # if true            

    print("Done: Found " + str(len(output)) + " results matching the applied filter(s)")

    if not args.print:
        max_file_size = 5000
        count = 0
        for i in range(0, len(output), max_file_size):

            if args.filename:
                custom_filename: str = args.filename[0][0]
                csv_out_path = Path(output_dir, Path(custom_filename + "_" + str(count) + ".csv"))
            else:
                csv_out_path = Path(output_dir, Path("filter_results_" + str(count) + ".csv"))

            with open(csv_out_path, "w", newline="", encoding='utf-8') as f:
                write = csv.writer(f)            
                write.writerow(header)
                write.writerows(output[i : i + max_file_size])  # writes data in blobs of max_file_size

            count += 1
    else:
        print(header_print)
        for row in output:
            print(", ".join(row))


if __name__ == "__main__":
    raise SystemExit(main())
