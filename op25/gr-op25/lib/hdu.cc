/* -*- C++ -*- */

/*
 * Copyright 2008 Steve Glass
 * 
 * This file is part of OP25.
 * 
 * OP25 is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 3, or (at your option)
 * any later version.
 * 
 * OP25 is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
 * or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public
 * License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with OP25; see the file COPYING.  If not, write to the Free
 * Software Foundation, Inc., 51 Franklin Street, Boston, MA
 * 02110-1301, USA.
 */

#include "hdu.h"
#include "op25_yank.h"
#include "pickle.h"
#include "value_string.h"

#include <iomanip>
#include <sstream>

using namespace std;

hdu::hdu(const_bit_queue& frame_body) :
   abstract_data_unit(frame_body)
{
}

hdu::~hdu()
{
}

string
hdu::duid_str() const
{
   return string("HDU");
}

std::string
hdu::snapshot() const
{
   pickle p;
   p.add("duid", duid_str());
   p.add("nac", nac_str());
   p.add("mfid", mfid_str());
   p.add("algid", algid_str());
   p.add("kid", kid_str());
   p.add("mi", mi_str());
   p.add("tgid", tgid_str());
   return p.to_string();
}

void
hdu::do_correct_errors(bit_vector& frame)
{
   apply_golay_correction(frame);
   apply_rs_correction(frame);
}

void
hdu::apply_golay_correction(bit_vector& frame)
{
   static const size_t NOF_GOLAY_CODEWORDS = 36, GOLAY_CODEWORD_SZ = 18;
   static const size_t GOLAY_CODEWORDS[NOF_GOLAY_CODEWORDS][GOLAY_CODEWORD_SZ] = {
      { 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 130, 131 },
      { 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 144, 145, 146, 147, 148, 149, 150, 151 },
      { 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 169 },
      { 170, 171, 172, 173, 174, 175, 176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187 },
      { 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205 },
      { 206, 207, 208, 209, 210, 211, 212, 213, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225 },
      { 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 240, 241, 242, 243 },
      { 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255, 256, 257, 258, 259, 260, 261 },
      { 262, 263, 264, 265, 266, 267, 268, 269, 270, 271, 272, 273, 274, 275, 276, 277, 278, 279 },
      { 280, 281, 282, 283, 284, 285, 288, 289, 290, 291, 292, 293, 294, 295, 296, 297, 298, 299 },
      { 300, 301, 302, 303, 304, 305, 306, 307, 308, 309, 310, 311, 312, 313, 314, 315, 316, 317 },
      { 318, 319, 320, 321, 322, 323, 324, 325, 326, 327, 328, 329, 330, 331, 332, 333, 334, 335 },
      { 336, 337, 338, 339, 340, 341, 342, 343, 344, 345, 346, 347, 348, 349, 350, 351, 352, 353 },
      { 354, 355, 356, 357, 360, 361, 362, 363, 364, 365, 366, 367, 368, 369, 370, 371, 372, 373 },
      { 374, 375, 376, 377, 378, 379, 380, 381, 382, 383, 384, 385, 386, 387, 388, 389, 390, 391 },
      { 392, 393, 394, 395, 396, 397, 398, 399, 400, 401, 402, 403, 404, 405, 406, 407, 408, 409 },
      { 410, 411, 412, 413, 414, 415, 416, 417, 418, 419, 420, 421, 422, 423, 424, 425, 426, 427 },
      { 428, 429, 432, 433, 434, 435, 436, 437, 438, 439, 440, 441, 442, 443, 444, 445, 446, 447 },
      { 448, 449, 450, 451, 452, 453, 454, 455, 456, 457, 458, 459, 460, 461, 462, 463, 464, 465 },
      { 466, 467, 468, 469, 470, 471, 472, 473, 474, 475, 476, 477, 478, 479, 480, 481, 482, 483 },
      { 484, 485, 486, 487, 488, 489, 490, 491, 492, 493, 494, 495, 496, 497, 498, 499, 500, 501 },
      { 504, 505, 506, 507, 508, 509, 510, 511, 512, 513, 514, 515, 516, 517, 518, 519, 520, 521 },
      { 522, 523, 524, 525, 526, 527, 528, 529, 530, 531, 532, 533, 534, 535, 536, 537, 538, 539 },
      { 540, 541, 542, 543, 544, 545, 546, 547, 548, 549, 550, 551, 552, 553, 554, 555, 556, 557 },
      { 558, 559, 560, 561, 562, 563, 564, 565, 566, 567, 568, 569, 570, 571, 572, 573, 576, 577 },
      { 578, 579, 580, 581, 582, 583, 584, 585, 586, 587, 588, 589, 590, 591, 592, 593, 594, 595 },
      { 596, 597, 598, 599, 600, 601, 602, 603, 604, 605, 606, 607, 608, 609, 610, 611, 612, 613 },
      { 614, 615, 616, 617, 618, 619, 620, 621, 622, 623, 624, 625, 626, 627, 628, 629, 630, 631 },
      { 632, 633, 634, 635, 636, 637, 638, 639, 640, 641, 642, 643, 644, 645, 648, 649, 650, 651 },
      { 652, 653, 654, 655, 656, 657, 658, 659, 660, 661, 662, 663, 664, 665, 666, 667, 668, 669 },
      { 670, 671, 672, 673, 674, 675, 676, 677, 678, 679, 680, 681, 682, 683, 684, 685, 686, 687 },
      { 688, 689, 690, 691, 692, 693, 694, 695, 696, 697, 698, 699, 700, 701, 702, 703, 704, 705 },
      { 706, 707, 708, 709, 710, 711, 712, 713, 714, 715, 716, 717, 720, 721, 722, 723, 724, 725 },
      { 726, 727, 728, 729, 730, 731, 732, 733, 734, 735, 736, 737, 738, 739, 740, 741, 742, 743 },
      { 744, 745, 746, 747, 748, 749, 750, 751, 752, 753, 754, 755, 756, 757, 758, 759, 760, 761 },
      { 762, 763, 764, 765, 766, 767, 768, 769, 770, 771, 772, 773, 774, 775, 776, 777, 778, 779 }
   };
   for(size_t i = 0; i < NOF_GOLAY_CODEWORDS; ++i) {
      uint32_t cw = extract(frame, GOLAY_CODEWORDS[i], GOLAY_CODEWORD_SZ);
//      uint32_t d = golay_decode(cw);
//      uint32 cw = golay_encode(cw);
//      yank_back(d, PAD_SZ, frame, GOLAY_CODEWORDS[i], GOLAY_DATA_SZ);
   }
}

void
hdu::apply_rs_correction(bit_vector& frame)
{
#if 0
   static itpp::Reed_Solomon rs(6, 8, true);

   const size_t rs_codeword[][6] = {
   };
   const size_t nof_codeword_bits = sizeof(codeword_bits) / sizeof(codeword_bits[0]);

#endif
}

uint16_t
hdu::frame_size_max() const
{
   return 792;
}

string
hdu::algid_str() const
{
   const size_t ALGID_BITS[] = {
      356, 357, 360, 361, 374, 375, 376, 377
   };
   const size_t ALGID_BITS_SZ = sizeof(ALGID_BITS) / sizeof(ALGID_BITS[0]);
   uint8_t algid = extract(frame_body(), ALGID_BITS, ALGID_BITS_SZ);
   return lookup(algid, ALGIDS, ALGIDS_SZ);
}

string
hdu::kid_str() const
{
   const size_t KID_BITS[] = {
      378, 379, 392, 393, 394, 395, 396, 397,
      410, 411, 412, 413, 414, 415, 428, 429
   };
   const size_t KID_BITS_SZ = sizeof(KID_BITS) / sizeof(KID_BITS[0]);
   uint16_t kid = extract(frame_body(), KID_BITS, KID_BITS_SZ);
   ostringstream os;
   os << hex << showbase << setfill('0') << setw(4) << kid;
   return os.str();
}

std::string
hdu::mi_str() const
{
   const size_t MI_BITS[] = {
      114, 115, 116, 117, 118, 119, 132, 133,
      134, 135, 136, 137, 152, 153, 154, 155,
      156, 157, 170, 171, 172, 173, 174, 175,
      188, 189, 190, 191, 192, 193, 206, 207,
      208, 209, 210, 211, 226, 227, 228, 229,
      230, 231, 244, 245, 246, 247, 248, 249,
      262, 263, 264, 265, 266, 267, 280, 281,
      282, 283, 284, 285, 300, 301, 302, 303,
      304, 305, 318, 319, 320, 321, 322, 323,
   };
   const size_t MI_BITS_SZ = sizeof(MI_BITS) / sizeof(MI_BITS[0]);

   uint8_t mi[9];
   extract(frame_body(), MI_BITS, MI_BITS_SZ, mi);
   ostringstream os;
   os << "0x";
   for(size_t i = 0; i < (sizeof(mi) / sizeof(mi[0])); ++i) {
      uint16_t octet = mi[i];
      os << hex << setfill('0') << setw(2) << octet;
   }
   return os.str();
}

string
hdu::mfid_str() const
{
   const size_t MFID_BITS[] = {
      336, 337, 338, 339, 340, 341, 354, 355
   };
   const size_t MFID_BITS_SZ = sizeof(MFID_BITS) / sizeof(MFID_BITS_SZ);
   uint8_t mfid = extract(frame_body(), MFID_BITS, MFID_BITS_SZ);
   return lookup(mfid, MFIDS, MFIDS_SZ);
}

string
hdu::nac_str() const
{
   const size_t NAC_BITS[] = {
      48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59
   };
   const size_t NAC_BITS_SZ = sizeof(NAC_BITS) / sizeof(NAC_BITS[0]);
   uint32_t nac = extract(frame_body(), NAC_BITS, NAC_BITS_SZ);
   return lookup(nac, NACS, NACS_SZ);
}

string
hdu::tgid_str() const
{
   const size_t TGID_BITS[] = {
      432, 433, 434, 435, 448, 449, 450, 451,
      452, 453, 466, 467, 468, 469, 470, 471
   };
   const size_t TGID_BITS_SZ = sizeof(TGID_BITS) / sizeof(TGID_BITS[0]);
   const uint16_t tgid = extract(frame_body(), TGID_BITS, TGID_BITS_SZ);
   ostringstream os;
   os << hex << showbase << setfill('0') << setw(4) << tgid;
   return os.str();
}
