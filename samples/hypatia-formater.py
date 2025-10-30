#!/usr/bin/python3

import argparse


def main(input: str, output: str, extended: bool = False) -> None:
    # Trace Format:          at,delay,stddev,min_link_cap,max_link_cap,queue_capacity,hops,dropratio,route_id
    #                        µs  µs    µs       bps            -          pkts         -      rel      int
    # LKM Format (simple):   <KEEP>,<LATENCY>,         <RATE>,<LOSS>,<LIMIT>\n
    # LKM Format (extended): <KEEP>,<LATENCY>,<JITTER>,<RATE>,<LOSS>,<LIMIT>,<DUP_PROB>,<DUP_DELAY>.<ROUTE_ID>\n
    #                          µs      ns        ns     bps    u32     pkts    u32          ns          u16
    with open(output, "w") as out_handle:
        if not extended:
            out_handle.write("keep,latency,rate,loss,limit\n")
        else:
            out_handle.write("keep,latency,jitter,rate,loss,limit,dup_prob,dub_delay,reorder_route\n")

        with open(input, "r") as input_handle:
            prev = 0
            for line in input_handle.readlines():
                if not line[0].isdigit():
                    continue
            
                keep, delay, stddev, min_link_cap, _, queue_cap, _, drops, route_id = line.replace("\n", "").split(",")
                keep = int(keep)
                if int(delay) == 0:
                    delay = 0
                else:
                    delay = max(0, int(delay) * 1000 + (20 * 1000 * 1000))
                stddev = int(float(stddev) * 1000)
                min_link_cap = int(float(min_link_cap))
                queue_cap = int(queue_cap)
                drops = int(round(float(drops) * 4294967295))
                route_id = int(route_id)

                if prev == 0:
                    prev = keep
                    continue

                if not extended:
                    out_handle.write(f"{keep - prev},{delay},{min_link_cap},{drops},{queue_cap}\n")
                else:
                    out_handle.write(f"{keep - prev},{delay},{stddev},{min_link_cap},{drops},{queue_cap},0,0,{route_id}\n")
                
                prev = keep


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("INPUT", type=str, help="Path to file in Hypatia-as-an-Emulator format")
    parser.add_argument("OUTPUT", type=str, help="Path to output file in demonstrator format")
    parser.add_argument("--format", "-f", choices=["simple", "extended"], type=str, default="simple",
                        help="Output file format type")
    args = parser.parse_args()

    main(args.INPUT, args.OUTPUT, args.format == "extended")
