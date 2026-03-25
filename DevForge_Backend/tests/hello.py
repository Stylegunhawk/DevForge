class Node:
  def __init__(self,value):
    self.value = value
    self.nxt = None
    self.prv = None

  def connect_nodes(self,node):
    self.nxt = node
    node.prv = self

class LinkedList:
  def __init__(self):
    self.head = None
    self.tail = None

  def insert_at_head(self,value):
    new_node = Node(value)
    if self.head is None:
      self.head = new_node
      self.tail = new_node
    else:
      new_node.connect_nodes(self.head)
      self.head = new_node

  def insert_at_tail(self,value):
    new_node = Node(value)
    if self.tail is None:
      self.head = new_node
      self.tail = new_node
    else:
      self.tail.connect_nodes(new_node)
      self.tail = new_node

  def delete_from_head(self):
    if self.head is None:
      return None
    deleted_node = self.head
    self.head = self.head.nxt
    if self.head is not None:
      self.head.prv = None
    else:
      self.tail = None
    return deleted_node.value

  def delete_from_tail(self):
    if self.tail is None:
      return None
    deleted_node = self.tail
    self.tail = self.tail.prv
    if self.tail is not None:
      self.tail.nxt = None
    else:
      self.head = None
    return deleted_node.value

  def traverse_forward(self):
    current_node = self.head
    while current_node is not None:
      print(current_node.value, end=" -> ")
      current_node = current_node.nxt
    print("None")

  def traverse_backward(self):
    current_node = self.tail
    while current_node is not None:
      print(current_node.value, end=" -> ")
      current_node = current_node.prv
    print("None")

  def search(self,value):
    current_node = self.head
    while current_node is not None:
      if current_node.value == value:
        return True
      current_node = current_node.nxt
    return False

  def insert_after(self,value,new_value):
    current_node = self.head
    while current_node is not None:
      if current_node.value == value:
        new_node = Node(new_value)
        new_node.connect_nodes(current_node.nxt)
        current_node.connect_nodes(new_node)
        return
      current_node = current_node.nxt
    print("Value not found")

  def insert_before(self,value,new_value):
    current_node = self.head
    while current_node is not None:
      if current_node.value == value:
        new_node = Node(new_value)
        new_node.connect_nodes(current_node)
        if current_node.prv is not None:
          current_node.prv.connect_nodes(new_node)
        else:
          self.head = new_node
        return
      current_node = current_node.nxt
    print("Value not found")

  def delete(self,value):
    current_node = self.head
    while current_node is not None:
      if current_node.value == value:
        if current_node.prv is not None:
          current_node.prv.connect_nodes(current_node.nxt)
        else:
          self.head = current_node.nxt
        if current_node.nxt is not None:
          current_node.nxt.prv = current_node.prv
        else:
          self.tail = current_node.prv
        return
      current_node = current_node.nxt
    print("Value not found")

  def reverse(self):
    current_node = self.head
    while current_node is not None:
      current_node.connect_nodes(current_node.prv)
      current_node = current_node.prv
    self.head, self.tail = self.tail, self.head

  def is_empty(self):
    return self.head is None

  def size(self):
    count = 0
    current_node = self.head
    while current_node is not None:
      count += 1
      current_node = current_node.nxt
    return count

  def clear(self):
    self.head = None
    self.tail = None

  def copy(self):
    new_list = LinkedList()
    current_node = self.head
    while current_node is not None:
      new_list.insert_at_tail(current_node.value)
      current_node = current_node.nxt
    return new_list

  def __str__(self):
    result = ""
    current_node = self.head
    while current_node is not None:
      result += str(current_node.value) + " -> "
      current_node = current_node.nxt
    result += "None"
    return result

  def __len__(self):
    return self.size()

  def __contains__(self,value):
    return self.search(value)

  def __getitem__(self,index):
    if index < 0:
      index = self.size() + index
    current_node = self.head
    for _ in range(index):
      if current_node is None:
        raise IndexError("Index out of range")
      current_node = current_node.nxt
    if current_node is None:
      raise IndexError("Index out of range")
    return current_node.value

  def __setitem__(self,index,value):
    if index < 0:
      index = self.size() + index
    current_node = self.head
    for _ in range(index):
      if current_node is None:
        raise IndexError("Index out of range")
      current_node = current_node.nxt
    if current_node is None:
      raise IndexError("Index out of range")
    current_node.value = value

  def __delitem__(self,index):
    self.delete(self[index])

  def __iter__(self):
    current_node = self.head
    while current_node is not None:
      yield current_node.value
      current_node = current_node.nxt

  def __reversed__(self):
    current_node = self.tail
    while current_node is not None:
      yield current_node.value
      current_node = current_node.prv

  def __add__(self,other):
    new_list = self.copy()
    current_node = other.head
    while current_node is not None:
      new_list.insert_at_tail(current_node.value)
      current_node = current_node.nxt
    return new_list

  def __iadd__(self,other):
    current_node = other.head
    while current_node is not None:
      self.insert_at_tail(current_node.value)
      current_node = current_node.nxt
    return self

  def __mul__(self,n):
    new_list = LinkedList()
    for _ in range(n):
      current_node = self.head
      while current_node is not None:
        new_list.insert_at_tail(current_node.value)
        current_node = current_node.nxt
    return new_list

  def __imul__(self,n):
    for _ in range(n):
      current

new_list = LinkedList()
new_list.insert_at_head(1)
new_list.insert_at_tail(2)
new_list.traverse_backward()
print(new_list)