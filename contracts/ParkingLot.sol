// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract ParkingLot {
    address public owner;
    
    // Đơn giá gửi xe mỗi giây (mặc định: 0.000001 ETH/giây, khoảng 0.0036 ETH/giờ)
    uint256 public parkingRate = 0.000001 ether;
    
    // Số tiền cọc cố định khi đặt chỗ (mặc định: 0.005 ETH)
    uint256 public depositAmount = 0.005 ether;

    // Thời gian hết hạn đặt chỗ (mặc định: 1 giờ)
    uint256 public constant BOOKING_EXPIRY = 1 hours;

    // Tracking tài chính an toàn
    uint256 public totalHeldDeposits;  // Tổng tiền cọc đang giữ (booking active + session active)
    uint256 public totalRevenue;       // Doanh thu thực tế đã tích lũy (có thể rút)

    struct Booking {
        address user;
        uint256 startTime;
        uint256 duration; // Thời gian đặt dự kiến (giây)
        bool active;
    }

    struct ParkingSession {
        address user;
        uint256 entryTime;
        uint256 deposit;
        bool active;
        string vehicleId; // Mã xe (từ AI hoặc nhập thủ công)
    }

    // Trạng thái đặt chỗ của từng ô đỗ (slotId => Booking)
    mapping(uint256 => Booking) public bookings;
    
    // Phiên đỗ xe hiện tại của từng ô đỗ (slotId => ParkingSession)
    mapping(uint256 => ParkingSession) public sessions;

    // Các sự kiện Blockchain
    event Booked(uint256 indexed slotId, address indexed user, uint256 startTime, uint256 duration, uint256 deposit);
    event BookingCancelled(uint256 indexed slotId, address indexed user, uint256 refundAmount);
    event ParkedIn(uint256 indexed slotId, address indexed user, uint256 entryTime, string vehicleId);
    event ParkedOut(uint256 indexed slotId, address indexed user, uint256 exitTime, uint256 actualFee, uint256 refundAmount, string vehicleId);
    event RateChanged(uint256 newRate);
    event DepositAmountChanged(uint256 newDeposit);
    event RevenueWithdrawn(address indexed owner, uint256 amount);

    modifier onlyOwner() {
        require(msg.sender == owner, "Chi co admin he thong moi co quyen");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    /**
     * @dev Người dùng thực hiện đặt chỗ trước cho một ô đỗ cụ thể và gửi cọc ETH
     * @param _slotId ID của ô đỗ xe
     * @param _duration Thời gian đỗ dự kiến (giây)
     */
    function bookSlot(uint256 _slotId, uint256 _duration) public payable {
        require(_slotId > 0, "Slot ID khong hop le");
        require(_duration > 0, "Thoi gian dat cho phai lon hon 0");
        require(msg.value >= depositAmount, "Tien coc gui len khong du");
        
        // Kiểm tra xem ô đỗ có đang đỗ hoặc đang được giữ chỗ hoạt động hay không
        require(!sessions[_slotId].active, "O do dang co xe do");
        
        if (bookings[_slotId].active) {
            // Cho phép đè đặt chỗ nếu lượt đặt chỗ cũ đã quá hạn mà không check-in
            require(block.timestamp > bookings[_slotId].startTime + BOOKING_EXPIRY, "O do dang duoc dat cho va chua het han");
            // Hoàn cọc cho booking cũ bị đè
            totalHeldDeposits -= depositAmount;
            payable(bookings[_slotId].user).transfer(depositAmount);
        }

        bookings[_slotId] = Booking({
            user: msg.sender,
            startTime: block.timestamp,
            duration: _duration,
            active: true
        });

        // Tracking tiền cọc
        totalHeldDeposits += depositAmount;

        // Trả lại phần tiền thừa nếu người dùng gửi nhiều hơn tiền cọc yêu cầu
        uint256 change = msg.value - depositAmount;
        if (change > 0) {
            payable(msg.sender).transfer(change);
        }

        emit Booked(_slotId, msg.sender, block.timestamp, _duration, depositAmount);
    }

    /**
     * @dev Người dùng tự hủy đặt chỗ (chỉ được thực hiện khi chưa check-in)
     */
    function cancelBooking(uint256 _slotId) public {
        require(bookings[_slotId].active, "Khong co luot dat cho hoat dong");
        require(bookings[_slotId].user == msg.sender, "Chi co nguoi dat cho moi co quyen huy");

        bookings[_slotId].active = false;
        totalHeldDeposits -= depositAmount;
        
        // Hoàn trả lại tiền cọc cho khách hàng
        payable(msg.sender).transfer(depositAmount);

        emit BookingCancelled(_slotId, msg.sender, depositAmount);
    }

    /**
     * @dev Hệ thống (AI hoặc Admin) kích hoạt xe đi vào ô đỗ
     */
    function checkIn(uint256 _slotId, string memory _vehicleId) public onlyOwner {
        require(_slotId > 0, "Slot ID khong hop le");
        require(!sessions[_slotId].active, "O do dang co xe do");
        
        address userAddress = owner; // Mặc định là vãng lai (thuộc về admin)
        uint256 sessionDeposit = 0;

        // Nếu ô đỗ đã được đặt chỗ từ trước và chưa quá hạn
        if (bookings[_slotId].active && block.timestamp <= bookings[_slotId].startTime + BOOKING_EXPIRY) {
            userAddress = bookings[_slotId].user;
            sessionDeposit = depositAmount;
            bookings[_slotId].active = false; // Xóa trạng thái đặt chỗ sau khi đã check-in
            // Chuyển deposit từ "held bookings" sang "session deposit" (vẫn giữ trong totalHeldDeposits)
        }

        sessions[_slotId] = ParkingSession({
            user: userAddress,
            entryTime: block.timestamp,
            deposit: sessionDeposit,
            active: true,
            vehicleId: _vehicleId
        });

        emit ParkedIn(_slotId, userAddress, block.timestamp, _vehicleId);
    }

    /**
     * @dev Hệ thống (AI hoặc Admin) ghi nhận xe rời bãi, tự động tính phí và hoàn cọc
     */
    function checkOut(uint256 _slotId) public onlyOwner {
        require(sessions[_slotId].active, "O do hien tai khong co xe");
        
        uint256 entryTime = sessions[_slotId].entryTime;
        address userAddress = sessions[_slotId].user;
        uint256 deposit = sessions[_slotId].deposit;
        string memory vehicleId = sessions[_slotId].vehicleId;
        
        // Tính toán thời gian thực tế và chi phí gửi xe
        uint256 duration = block.timestamp > entryTime ? block.timestamp - entryTime : 0;
        uint256 fee = duration * parkingRate;
        
        uint256 refundAmount = 0;
        
        if (deposit > 0) {
            // Xe đã đặt chỗ trước (có cọc)
            if (fee > deposit) {
                fee = deposit; // Cấn trừ hết cọc
            } else {
                refundAmount = deposit - fee;
            }
            totalHeldDeposits -= deposit;
            totalRevenue += fee;
        } else {
            // Xe vãng lai: tính phí nhưng ghi nhận doanh thu = 0 on-chain 
            // (phí hiển thị trong event để thu tiền mặt ngoài đời thực)
            // Không cộng vào totalRevenue vì không có ETH thực sự được nạp
        }

        // Thực hiện tương tác tài chính (Checks-Effects-Interactions pattern)
        sessions[_slotId].active = false;

        if (refundAmount > 0 && userAddress != owner) {
            payable(userAddress).transfer(refundAmount);
        }

        emit ParkedOut(_slotId, userAddress, block.timestamp, fee, refundAmount, vehicleId);
    }

    /**
     * @dev Thay đổi đơn giá đỗ xe
     */
    function setRate(uint256 _newRate) public onlyOwner {
        parkingRate = _newRate;
        emit RateChanged(_newRate);
    }

    /**
     * @dev Thay đổi mức tiền cọc tối thiểu để đặt chỗ
     */
    function setDepositAmount(uint256 _newDeposit) public onlyOwner {
        depositAmount = _newDeposit;
        emit DepositAmountChanged(_newDeposit);
    }

    /**
     * @dev Admin rút tiền doanh thu đỗ xe tích lũy (CHỈ rút phần revenue, KHÔNG rút tiền cọc khách hàng)
     */
    function withdrawRevenues() public onlyOwner {
        require(totalRevenue > 0, "Khong co doanh thu de rut");
        uint256 amount = totalRevenue;
        totalRevenue = 0;
        payable(owner).transfer(amount);
        emit RevenueWithdrawn(owner, amount);
    }

    /**
     * @dev Lấy thông tin trạng thái đặt chỗ hiện tại
     */
    function getBookingStatus(uint256 _slotId) public view returns (address user, uint256 startTime, uint256 duration, bool active) {
        Booking memory b = bookings[_slotId];
        return (b.user, b.startTime, b.duration, b.active);
    }

    /**
     * @dev Lấy thông tin phiên đỗ xe hiện tại
     */
    function getSessionStatus(uint256 _slotId) public view returns (
        address user, uint256 entryTime, uint256 deposit, bool active, string memory vehicleId
    ) {
        ParkingSession memory s = sessions[_slotId];
        return (s.user, s.entryTime, s.deposit, s.active, s.vehicleId);
    }
}
