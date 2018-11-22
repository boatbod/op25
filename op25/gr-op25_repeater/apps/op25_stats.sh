#!/bin/sh

# op25_stats.sh -- 20 November 2017
# Copyright John Ackermann N8UR -- jra@febo.com
# Licensed under GNU General Public License V2 or later
#
# parse log file from op25 rx.py program
# and generate statistics.
#
# usage: op25_stats.sh logfile tsv_tagfile

echo ""

# list of frequencies used
echo "Generating list of frequencies used: op25-freqs-used.txt"
echo "# Frequencies Used" > op25-freqs-used.txt
grep 'new freq:' $1 | cut -d" " -f4 | sort -n >> op25-freqs-used.txt

# control channels used, and time of switch
echo "Generating list of control channels used: op25-cc-used.txt"
echo "# Control Channels Used" > op25-cc-used.txt
grep 'set control channel:' $1 | cut -d" " -f1,5 >> op25-cc-used.txt

# list of new talkgroups seen
echo "Generating list of new talkgroups seen: op25-new-tgids.txt"
echo "# Newly Seen Talkgroups" > op25-new-tgids.txt
grep 'new tgid:' $1 | cut -d" " -f4- | sort -n >> op25-new-tgids.txt

# histogram of talkgroups
echo "Munging log and tag files..."
temp1=$(mktemp)
temp2=$(mktemp)
#grep 'set tgid:' $1 | cut -d" " -f4- | sort -k 1b,1 | uniq -c \
grep 'set tgid=' $1 | sed s/^.*tgid=// | sed s/,.*$// | sort -k 1b,1 | uniq -c \
    | sed -r 's/^ +([0-9]+) /\1\t/' > $temp1

sort -k 1b,1 $2 \
    | sed -e "s/[[:space:]]\+/ /g"  \
    | sed -e "s/ /\t/" \
 > $temp2

# denominator for percentages
cmd_cnt=`grep 'set tgid=' $1 | wc -l` 

echo "Writing op25-tgid-frequency.txt"
echo "# Talkgroup Frequency Analysis" > op25-tgid-frequency.txt
echo "# PCT   Count   TGID    Description" >> op25-tgid-frequency.txt
join -1 2 -2 1 -a 1 -o 1.1,1.2,2.2,2.3,2.4,2.5,2.6,2.7,2.8,2.9,2.10,2.11,2.12,2.13 \
     $temp1 \
     $temp2 \
     | sort -nr \
     | sed 's/ /\t/' | sed 's/ /\t/' \
     | awk -v cmd_cnt="$cmd_cnt" \
         '{FS="\t"} {printf "%2.3f\t%d\t%d\t%s %s %s %s %s %s %s\n",($1/cmd_cnt)*100,$1,$2,$3,$4,$5,$6,$7,$8,$9}' \
     | sed 's/[ \t]*$//' \
     >> op25-tgid-frequency.txt

# Frequency Analysis of unknown TGIDs
echo "Writing op25-tagless-frequency.txt"
echo "# Talkgroups without tags" > op25-tagless-frequency.txt
echo "# PCT   Count   TGID" >> op25-tagless-frequency.txt
awk '{FS="\t"} NR>2 {if(NF<4)  print $0}' \
    op25-tgid-frequency.txt \
    >> op25-tagless-frequency.txt

# Unknown TGIDs sorted numerically
echo "Writing op25-tagless-numeric.txt"
echo "# Tagless talkgroups sorted numerically" > op25-tagless-numeric.txt
echo "# TGID  PCT     Count" >> op25-tagless-numeric.txt
awk '{FS=OFS="\t"} NR>2 {print $3,$1,$2}' op25-tagless-frequency.txt \
    | sort -n >> op25-tagless-numeric.txt

# show activity (number of commands) per five minute interval
echo "Generating activity histogram: op25-activity.txt"
start=`grep 'set tgid:' $1 | head -n1 | cut -d" " -f1 | cut -c1-10`
echo "# Commands sent in prior 5 minutes (300 seconds)" > op25-activity.txt
echo "# Starting time (Unix epoch): $start" >> op25-activity.txt
echo "" >> op25-activity.txt
cut -c1-10 $1 | awk '{print int($1/300)}' | sort -n | uniq -c \
    | cut -d" " -f4- | sort -k2 -n \
    | awk '{if ($2 > 0) print $2*300,$1}' >> op25-activity.txt

# clean up
echo "Cleaning up..."
echo ""
rm $temp1 $temp2
