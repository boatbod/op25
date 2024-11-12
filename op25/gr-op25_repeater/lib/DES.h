/* Written by Ali Elmasry, adapted by Joey Absi */
#ifndef _DES_
#define _DES_

#include <string>
#include <vector>
#include <bitset>
#include <unordered_map>
#include <sstream>
#include <iomanip>


class DES {
 private:
  
  
 public:
  std::string hex2bin(std::string s);
  std::string bin2hex(std::string s);
  std::string permute(std::string k, int* arr, int n);
  std::string shift_left(std::string k, int shifts);
  std::string xor_(std::string a, std::string b);
  std::string encrypt(std::string pt, std::vector<std::string> rkb, std::vector<std::string> rk);
  void string2ByteArray(const std::string& s, uint8_t array[], int offset);
  std::string byteArray2string(uint8_t array[]);
  
};

#endif
