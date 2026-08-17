#include <unistd.h>
#include <cerrno>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

int main(int argc, char** argv) {
    std::vector<std::string> text;
    text.emplace_back("python3");
    text.emplace_back("exp-07/src/r0.py");
    for (int i = 1; i < argc; ++i) text.emplace_back(argv[i]);
    std::vector<char*> args;
    args.reserve(text.size() + 1);
    for (auto& item : text) args.push_back(item.data());
    args.push_back(nullptr);
    execvp(args[0], args.data());
    std::cerr << "execvp failed: " << std::strerror(errno) << "\n";
    return 127;
}
